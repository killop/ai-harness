#!/usr/bin/env python3
"""
searcher.py — Find anything. Exact words.

Hybrid search: direct drawer retrieval is always the floor, and closet hits can
only add a ranking boost when they agree. The drawer path also has a
multilingual lexical fallback so mixed Chinese/English technical queries still
rank well when embeddings underperform.
"""

import hashlib
import logging
import math
import re
import unicodedata
from pathlib import Path
from typing import Dict, List

from .palace import get_closets_collection, get_collection

# Closet pointer line format: "topic|entities|→drawer_id_a,drawer_id_b"
# Multiple lines may join with newlines inside one closet document.
_CLOSET_DRAWER_REF_RE = re.compile(r"→([\w,]+)")

logger = logging.getLogger("mempalace_mcp")

_LATIN_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[._:/-][A-Za-z0-9]+)*")
_CJK_SEQ_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]+")
_WHITESPACE_RE = re.compile(r"\s+")
_COMPACT_RE = re.compile(r"[\s._:/-]+")
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_STRUCTURAL_QUERY_MARKERS = (
    "adr",
    "rfc",
    "spec",
    "design",
    "architecture",
    "migration",
    "schema",
    "api",
    "接口",
    "设计",
    "文档",
    "架构",
    "方案",
    "决策",
    "取舍",
    "回滚",
)
_LEXICAL_SCAN_LIMIT = 240
_VECTOR_CANDIDATE_FACTOR = 4
_MIN_VECTOR_CANDIDATES = 20


class SearchError(Exception):
    """Raised when search cannot proceed (e.g. no palace found)."""


def build_where_filter(wing: str = None, room: str = None) -> dict:
    """Build ChromaDB where filter for wing/room filtering."""
    if wing and room:
        return {"$and": [{"wing": wing}, {"room": room}]}
    elif wing:
        return {"wing": wing}
    elif room:
        return {"room": room}
    return {}


def _normalize_text(text: str) -> str:
    """Normalize text for multilingual lexical matching."""
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKC", text).lower()
    return _WHITESPACE_RE.sub(" ", text).strip()


def _compact_text(text: str) -> str:
    """Remove separators so query/file matches survive punctuation differences."""
    return _COMPACT_RE.sub("", _normalize_text(text))


def _split_identifier(token: str) -> List[str]:
    """Split technical identifiers like PaymentGateway or auth-service."""
    token = _CAMEL_BOUNDARY_RE.sub(" ", token)
    for sep in ("_", "-", ".", "/", ":"):
        token = token.replace(sep, " ")
    return [part for part in token.split() if len(part) >= 2]


def _cjk_subtokens(text: str) -> List[str]:
    """Generate exact CJK spans plus short n-grams for mixed-language matching."""
    tokens: List[str] = []
    for seq in _CJK_SEQ_RE.findall(_normalize_text(text)):
        tokens.append(seq)
        for n in (2, 3):
            if len(seq) >= n:
                tokens.extend(seq[i : i + n] for i in range(len(seq) - n + 1))
    return tokens


def _tokenize_text(text: str) -> List[str]:
    """Tokenize prose, identifiers, and CJK sequences for lexical scoring."""
    normalized = _normalize_text(text)
    seen = set()
    tokens: List[str] = []

    for token in _LATIN_TOKEN_RE.findall(normalized):
        if len(token) >= 2 and token not in seen:
            seen.add(token)
            tokens.append(token)
        for part in _split_identifier(token):
            part = part.lower()
            if part not in seen:
                seen.add(part)
                tokens.append(part)

    for token in _cjk_subtokens(normalized):
        if token not in seen:
            seen.add(token)
            tokens.append(token)

    return tokens


def _tokenize(text: str) -> List[str]:
    """Shared tokenization for BM25 and drawer-grep scoring."""
    return _tokenize_text(text)


def _build_query_profile(query: str) -> Dict[str, object]:
    """Precompute normalized query forms for hybrid ranking."""
    normalized = _normalize_text(query)
    return {
        "raw": query,
        "normalized": normalized,
        "compact": _compact_text(normalized),
        "tokens": _tokenize(query),
        "contains_cjk": bool(_CJK_SEQ_RE.search(normalized)),
        "looks_structural": any(marker in normalized for marker in _STRUCTURAL_QUERY_MARKERS),
    }


def _bm25_scores(
    query: str,
    documents: list,
    k1: float = 1.5,
    b: float = 0.75,
) -> list:
    """Compute Okapi-BM25 scores for ``query`` against each document."""
    n_docs = len(documents)
    query_terms = set(_tokenize(query))
    if not query_terms or n_docs == 0:
        return [0.0] * n_docs

    tokenized = [_tokenize(d) for d in documents]
    doc_lens = [len(toks) for toks in tokenized]
    if not any(doc_lens):
        return [0.0] * n_docs
    avgdl = sum(doc_lens) / n_docs or 1.0

    df = {term: 0 for term in query_terms}
    for toks in tokenized:
        seen = set(toks) & query_terms
        for term in seen:
            df[term] += 1

    idf = {
        term: math.log((n_docs - df[term] + 0.5) / (df[term] + 0.5) + 1) for term in query_terms
    }

    scores = []
    for toks, dl in zip(tokenized, doc_lens):
        if dl == 0:
            scores.append(0.0)
            continue
        tf = {}
        for token in toks:
            if token in query_terms:
                tf[token] = tf.get(token, 0) + 1
        score = 0.0
        for term, freq in tf.items():
            num = freq * (k1 + 1)
            den = freq + k1 * (1 - b + b * dl / avgdl)
            score += idf[term] * num / den
        scores.append(score)
    return scores


def _hybrid_rank(
    results: list,
    query: str,
    vector_weight: float = 0.6,
    bm25_weight: float = 0.4,
) -> list:
    """Re-rank ``results`` by vector similarity, BM25, and closet boost."""
    if not results:
        return results

    docs = [r.get("text", "") for r in results]
    bm25_raw = _bm25_scores(query, docs)
    max_bm25 = max(bm25_raw) if bm25_raw else 0.0
    bm25_norm = [s / max_bm25 for s in bm25_raw] if max_bm25 > 0 else [0.0] * len(bm25_raw)

    scored = []
    for result, raw, norm in zip(results, bm25_raw, bm25_norm):
        vec_sim = max(0.0, 1.0 - result.get("distance", 1.0))
        closet_boost = result.get("closet_boost", 0.0)
        result["bm25_score"] = round(raw, 3)
        scored.append((vector_weight * vec_sim + bm25_weight * norm + closet_boost, result))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    results[:] = [result for _, result in scored]
    return results


def _safe_first_nested_list(value) -> list:
    """Return the first nested list from Chroma query results."""
    if isinstance(value, list) and value:
        return value[0] if isinstance(value[0], list) else []
    return []


def _safe_list(value) -> list:
    """Return a plain list from Chroma get results."""
    return value if isinstance(value, list) else []


def _candidate_key(drawer_id: str, doc: str, meta: dict) -> str:
    """Stable dedupe key across vector and lexical candidates."""
    if drawer_id:
        return drawer_id
    source = meta.get("source_file", "")
    chunk = meta.get("chunk_index", "")
    digest = hashlib.sha1(doc.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{source}::{chunk}::{digest}"


def _normalize_query_rows(results: dict) -> List[dict]:
    """Flatten Chroma query() output into candidate dicts."""
    docs = _safe_first_nested_list(results.get("documents"))
    metas = _safe_first_nested_list(results.get("metadatas"))
    dists = _safe_first_nested_list(results.get("distances"))
    ids = _safe_first_nested_list(results.get("ids"))

    rows = []
    for idx, doc in enumerate(docs):
        if not isinstance(doc, str):
            continue
        meta = metas[idx] if idx < len(metas) and isinstance(metas[idx], dict) else {}
        dist = dists[idx] if idx < len(dists) and isinstance(dists[idx], (int, float)) else None
        drawer_id = ids[idx] if idx < len(ids) and isinstance(ids[idx], str) else None
        rows.append(
            {
                "id": drawer_id,
                "doc": doc,
                "meta": meta,
                "distance": dist,
                "source": "vector",
            }
        )
    return rows


def _normalize_get_rows(results: dict) -> List[dict]:
    """Flatten Chroma get() output into candidate dicts."""
    if not isinstance(results, dict):
        return []

    docs = _safe_list(results.get("documents"))
    metas = _safe_list(results.get("metadatas"))
    ids = _safe_list(results.get("ids"))

    rows = []
    for idx, doc in enumerate(docs):
        if not isinstance(doc, str):
            continue
        meta = metas[idx] if idx < len(metas) and isinstance(metas[idx], dict) else {}
        drawer_id = ids[idx] if idx < len(ids) and isinstance(ids[idx], str) else None
        rows.append(
            {
                "id": drawer_id,
                "doc": doc,
                "meta": meta,
                "distance": None,
                "source": "lexical",
            }
        )
    return rows


def _score_text_matches(tokens: List[str], haystack: str) -> tuple[float, int]:
    """Score query token matches within one text region."""
    score = 0.0
    matched = 0
    for token in tokens:
        if token not in haystack:
            continue
        matched += 1
        occurrences = min(haystack.count(token), 3)
        if _CJK_SEQ_RE.search(token):
            base = 1.2
        elif len(token) >= 6:
            base = 1.1
        elif len(token) >= 4:
            base = 0.9
        else:
            base = 0.7
        score += base + (occurrences - 1) * 0.2
    return score, matched


def _score_lexical_match(profile: Dict[str, object], doc: str, meta: dict) -> float:
    """Lexical score that understands CJK, file names, and design-doc structure."""
    tokens = profile["tokens"]
    if not tokens and not profile["normalized"]:
        return 0.0

    doc_norm = _normalize_text(doc)
    file_norm = _normalize_text(Path(meta.get("source_file", "")).name)
    room_norm = _normalize_text(meta.get("room", ""))
    wing_norm = _normalize_text(meta.get("wing", ""))
    meta_norm = " ".join(part for part in (file_norm, room_norm, wing_norm) if part)

    doc_score, doc_matches = _score_text_matches(tokens, doc_norm)
    meta_score, meta_matches = _score_text_matches(tokens, meta_norm)

    total_unique = len(set(tokens)) or 1
    coverage = min(1.0, (doc_matches + meta_matches) / total_unique)
    score = min(0.65, doc_score * 0.08) + min(0.25, meta_score * 0.12) + coverage * 0.35

    normalized_query = profile["normalized"]
    compact_query = profile["compact"]
    if normalized_query and normalized_query in doc_norm:
        score += 0.25
    if normalized_query and normalized_query in meta_norm:
        score += 0.18
    if compact_query and len(compact_query) >= 4:
        if compact_query in _compact_text(doc):
            score += 0.18
        if compact_query in _compact_text(meta_norm):
            score += 0.12

    if profile["looks_structural"]:
        structural_hits = (
            "design doc",
            "technical design",
            "architecture",
            "trade-off",
            "tradeoff",
            "rollback",
            "rationale",
            "decision",
            "adr",
            "rfc",
            "设计",
            "架构",
            "决策",
            "方案",
            "风险",
            "回滚",
        )
        if any(term in doc_norm or term in meta_norm for term in structural_hits):
            score += 0.1

    return round(min(score, 1.0), 4)


def _merge_candidates(*candidate_groups: List[dict]) -> List[dict]:
    """Merge vector and lexical candidates without duplicates."""
    merged = {}
    for group in candidate_groups:
        for row in group:
            key = _candidate_key(row.get("id"), row["doc"], row.get("meta", {}))
            existing = merged.get(key)
            if existing is None:
                merged[key] = row
                continue
            if existing.get("distance") is None and row.get("distance") is not None:
                existing["distance"] = row["distance"]
            if existing.get("source") != "hybrid" and row.get("distance") is not None:
                existing["source"] = "hybrid"
    return list(merged.values())


def _should_expand_candidates(profile: Dict[str, object], vector_rows: List[dict], n_results: int) -> bool:
    """Decide whether to scan extra docs for lexical fallback."""
    return (
        not vector_rows
        or len(vector_rows) < n_results
        or profile["contains_cjk"]
        or profile["looks_structural"]
    )


def _fetch_lexical_candidates(collection, where: dict, limit: int) -> List[dict]:
    """Fetch a bounded slice of docs for lexical fallback."""
    rows: List[dict] = []
    offset = 0
    batch_size = min(100, limit)

    while offset < limit:
        kwargs = {
            "include": ["documents", "metadatas"],
            "limit": min(batch_size, limit - offset),
            "offset": offset,
        }
        if where:
            kwargs["where"] = where

        try:
            batch = collection.get(**kwargs)
        except Exception:
            break

        batch_rows = _normalize_get_rows(batch)
        if not batch_rows:
            break

        rows.extend(batch_rows)
        offset += len(batch_rows)
        if len(batch_rows) < kwargs["limit"]:
            break

    return rows


def _rank_candidates(
    profile: Dict[str, object],
    candidates: List[dict],
    n_results: int,
    max_distance: float,
) -> dict:
    """Apply hybrid ranking and build final hit payloads."""
    lexical_weight = 0.62 if (profile["contains_cjk"] or profile["looks_structural"]) else 0.38
    semantic_weight = 1.0 - lexical_weight

    ranked = []
    for row in candidates:
        meta = row.get("meta", {})
        doc = row["doc"]
        semantic_similarity = (
            round(max(0.0, 1 - row["distance"]), 4) if row.get("distance") is not None else 0.0
        )
        lexical_similarity = _score_lexical_match(profile, doc, meta)
        combined_similarity = round(
            semantic_similarity * semantic_weight + lexical_similarity * lexical_weight,
            4,
        )
        rank_score = combined_similarity
        similarity = max(semantic_similarity, combined_similarity, lexical_similarity)
        distance = row["distance"]
        if distance is None:
            distance = round(max(0.0, 1 - similarity), 4)

        ranked.append(
            {
                "text": doc,
                "wing": meta.get("wing", "unknown"),
                "room": meta.get("room", "unknown"),
                "source_file": Path(meta.get("source_file", "?")).name,
                "similarity": round(similarity, 3),
                "distance": round(distance, 4),
                "rank_score": round(rank_score, 4),
                "lexical_similarity": lexical_similarity,
                "semantic_similarity": round(semantic_similarity, 4),
                "metadata": meta,
                "retrieval": "hybrid"
                if row.get("source") == "hybrid" or (semantic_similarity and lexical_similarity)
                else row.get("source", "vector"),
            }
        )

    ranked.sort(
        key=lambda hit: (
            hit["rank_score"],
            hit["lexical_similarity"],
            hit["semantic_similarity"],
            hit["source_file"],
        ),
        reverse=True,
    )

    total_before_filter = len(ranked)
    hits = []
    for hit in ranked:
        if max_distance > 0.0 and hit["distance"] > max_distance:
            continue
        hits.append(hit)
        if len(hits) >= n_results:
            break

    return {"total_before_filter": total_before_filter, "results": hits}


def _extract_drawer_ids_from_closet(closet_doc: str) -> list:
    """Parse all `→drawer_id_a,drawer_id_b` pointers out of a closet document."""
    seen = {}
    for match in _CLOSET_DRAWER_REF_RE.findall(closet_doc):
        for drawer_id in match.split(","):
            drawer_id = drawer_id.strip()
            if drawer_id and drawer_id not in seen:
                seen[drawer_id] = None
    return list(seen.keys())


def _expand_with_neighbors(drawers_col, matched_doc: str, matched_meta: dict, radius: int = 1):
    """Expand a matched drawer with its sibling chunks in the same source file."""
    source_file = matched_meta.get("source_file")
    chunk_index = matched_meta.get("chunk_index")
    if not source_file or not isinstance(chunk_index, int):
        return {"text": matched_doc, "drawer_index": chunk_index, "total_drawers": None}

    target_indexes = [chunk_index + offset for offset in range(-radius, radius + 1)]
    try:
        neighbors = drawers_col.get(
            where={
                "$and": [
                    {"source_file": source_file},
                    {"chunk_index": {"$in": target_indexes}},
                ]
            },
            include=["documents", "metadatas"],
        )
    except Exception:
        return {"text": matched_doc, "drawer_index": chunk_index, "total_drawers": None}

    indexed_docs = []
    for doc, meta in zip(neighbors.get("documents") or [], neighbors.get("metadatas") or []):
        neighbor_index = meta.get("chunk_index")
        if isinstance(neighbor_index, int):
            indexed_docs.append((neighbor_index, doc))
    indexed_docs.sort(key=lambda pair: pair[0])

    combined_text = matched_doc if not indexed_docs else "\n\n".join(doc for _, doc in indexed_docs)

    total_drawers = None
    try:
        all_meta = drawers_col.get(where={"source_file": source_file}, include=["metadatas"])
        ids = all_meta.get("ids") or []
        total_drawers = len(ids) if ids else None
    except Exception:
        pass

    return {
        "text": combined_text,
        "drawer_index": chunk_index,
        "total_drawers": total_drawers,
    }


def _search_collection(
    collection,
    query: str,
    wing: str = None,
    room: str = None,
    n_results: int = 5,
    max_distance: float = 0.0,
) -> dict:
    """Run drawer search with lexical reranking and bounded fallback."""
    where = build_where_filter(wing, room)
    query_profile = _build_query_profile(query)
    candidate_count = max(_MIN_VECTOR_CANDIDATES, n_results * _VECTOR_CANDIDATE_FACTOR)

    try:
        kwargs = {
            "query_texts": [query],
            "n_results": candidate_count,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        query_rows = _normalize_query_rows(collection.query(**kwargs))
    except Exception as e:
        return {"error": f"Search error: {e}"}

    all_rows = list(query_rows)
    if _should_expand_candidates(query_profile, query_rows, n_results):
        lexical_limit = max(candidate_count, _LEXICAL_SCAN_LIMIT)
        lexical_rows = _fetch_lexical_candidates(collection, where=where, limit=lexical_limit)
        all_rows = _merge_candidates(query_rows, lexical_rows)

    return _rank_candidates(query_profile, all_rows, n_results=n_results, max_distance=max_distance)


def search(query: str, palace_path: str, wing: str = None, room: str = None, n_results: int = 5):
    """CLI search. Prints verbatim drawer content."""
    result = search_memories(
        query=query,
        palace_path=palace_path,
        wing=wing,
        room=room,
        n_results=n_results,
    )
    if "error" in result:
        if result["error"] == "No palace found":
            print(f"\n  No palace found at {palace_path}")
            print("  Run: mempalace init <dir> then mempalace mine <dir>")
            raise SearchError(f"No palace found at {palace_path}")
        print(f"\n  {result['error']}")
        raise SearchError(result["error"])

    hits = result["results"]
    if not hits:
        print(f'\n  No results found for: "{query}"')
        return

    print(f"\n{'=' * 60}")
    print(f'  Results for: "{query}"')
    if wing:
        print(f"  Wing: {wing}")
    if room:
        print(f"  Room: {room}")
    print(f"{'=' * 60}\n")

    for i, hit in enumerate(hits, 1):
        print(f"  [{i}] {hit['wing']} / {hit['room']}")
        print(f"      Source: {hit['source_file']}")
        print(f"      Match:  {hit['similarity']}")
        print()
        for line in hit["text"].strip().split("\n"):
            print(f"      {line}")
        print()
        print(f"  {'─' * 56}")

    print()


def search_memories(
    query: str,
    palace_path: str,
    wing: str = None,
    room: str = None,
    n_results: int = 5,
    max_distance: float = 0.0,
) -> dict:
    """Programmatic search — returns a dict instead of printing."""
    try:
        drawers_col = get_collection(palace_path, create=False)
    except Exception as e:
        logger.error("No palace found at %s: %s", palace_path, e)
        return {
            "error": "No palace found",
            "hint": "Run: mempalace init <dir> && mempalace mine <dir>",
        }

    where = build_where_filter(wing, room)

    ranked = _search_collection(
        drawers_col,
        query=query,
        wing=wing,
        room=room,
        n_results=max(_MIN_VECTOR_CANDIDATES, n_results * 3),
        max_distance=max_distance,
    )
    if "error" in ranked:
        return ranked

    hits = ranked["results"]

    closet_boost_by_source = {}
    try:
        closets_col = get_closets_collection(palace_path, create=False)
        ckwargs = {
            "query_texts": [query],
            "n_results": n_results * 2,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            ckwargs["where"] = where
        closet_results = closets_col.query(**ckwargs)
        for rank, (closet_doc, closet_meta, closet_distance) in enumerate(
            zip(
                _safe_first_nested_list(closet_results.get("documents")),
                _safe_first_nested_list(closet_results.get("metadatas")),
                _safe_first_nested_list(closet_results.get("distances")),
            )
        ):
            source_file = closet_meta.get("source_file", "")
            if source_file and source_file not in closet_boost_by_source:
                closet_boost_by_source[source_file] = (rank, closet_distance, closet_doc[:200])
    except Exception:
        pass

    closet_rank_boosts = [0.40, 0.25, 0.15, 0.08, 0.04]
    closet_distance_cap = 1.5

    for hit in hits:
        source_file = hit.get("metadata", {}).get("source_file", "") or ""
        boost = 0.0
        matched_via = "drawer"
        closet_preview = None
        if source_file in closet_boost_by_source:
            closet_rank, closet_distance, preview = closet_boost_by_source[source_file]
            if closet_distance <= closet_distance_cap and closet_rank < len(closet_rank_boosts):
                boost = closet_rank_boosts[closet_rank]
                matched_via = "drawer+closet"
                closet_preview = preview

        hit["closet_boost"] = round(boost, 3)
        hit["matched_via"] = matched_via
        hit["effective_distance"] = round(max(0.0, hit["distance"] - boost), 4)
        hit["_source_file_full"] = source_file
        hit["_closet_rank_score"] = round(hit["rank_score"] + boost, 4)
        if closet_preview:
            hit["closet_preview"] = closet_preview

    hits.sort(
        key=lambda hit: (
            hit["_closet_rank_score"],
            hit["lexical_similarity"],
            hit["semantic_similarity"],
            hit["source_file"],
        ),
        reverse=True,
    )
    hits = hits[: max(n_results * 3, n_results)]

    max_hydration_chars = 10000
    query_terms = set(_tokenize(query))
    for hit in hits:
        if hit["matched_via"] == "drawer":
            continue
        source_file = hit.get("_source_file_full") or ""
        if not source_file:
            continue
        try:
            source_drawers = drawers_col.get(
                where={"source_file": source_file},
                include=["documents", "metadatas"],
            )
        except Exception:
            continue
        docs = source_drawers.get("documents") or []
        metas = source_drawers.get("metadatas") or []
        if len(docs) <= 1:
            continue

        indexed = []
        for idx, (doc, meta) in enumerate(zip(docs, metas)):
            chunk_index = meta.get("chunk_index", idx) if isinstance(meta, dict) else idx
            if not isinstance(chunk_index, int):
                chunk_index = idx
            indexed.append((chunk_index, doc))
        indexed.sort(key=lambda pair: pair[0])
        ordered_docs = [doc for _, doc in indexed]

        best_idx = 0
        best_score = -1
        for idx, doc in enumerate(ordered_docs):
            doc_norm = _normalize_text(doc)
            score = sum(1 for token in query_terms if token in doc_norm)
            if score > best_score:
                best_score = score
                best_idx = idx

        start = max(0, best_idx - 1)
        end = min(len(ordered_docs), best_idx + 2)
        expanded = "\n\n".join(ordered_docs[start:end])
        if len(expanded) > max_hydration_chars:
            expanded = (
                expanded[:max_hydration_chars]
                + f"\n\n[...truncated. {len(ordered_docs)} total drawers. "
                "Use mempalace_get_drawer for full content.]"
            )
        hit["text"] = expanded
        hit["drawer_index"] = best_idx
        hit["total_drawers"] = len(ordered_docs)

    hits = _hybrid_rank(hits, query)
    hits = hits[:n_results]

    for hit in hits:
        hit.pop("_source_file_full", None)
        hit.pop("_closet_rank_score", None)

    return {
        "query": query,
        "filters": {"wing": wing, "room": room},
        "total_before_filter": ranked["total_before_filter"],
        "results": hits,
    }
