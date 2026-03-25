import os
import json
import copy
import math
import random
import re
from collections import defaultdict
from .utils import *
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

TOC_IGNORED_LINES = {
    "table of contents",
    "contents",
}
GENERIC_TOC_TITLES = {
    "overview",
    "background",
    "design goals",
    "implementation details",
    "testing notes",
    "detailed findings",
    "summary",
    "conclusion",
}


def _stage_log(stage: str, message: str, logger=None, **details):
    if not is_debug_logs_enabled():
        return
    detail_text = ""
    if details:
        ordered = ", ".join(f"{key}={details[key]}" for key in sorted(details))
        detail_text = f" | {ordered}"
    print(f"[{stage}] {message}{detail_text}")
    if logger:
        logger.info({"stage": stage, "message": message, **details})


def _heuristic_toc_detect(content: str | None):
    text = str(content or "")
    lines = [_normalize_toc_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return None

    joined = "\n".join(lines[:12]).lower()
    has_contents_header = any(
        line.lower() in TOC_IGNORED_LINES or line.lower().startswith("table of contents")
        for line in lines[:5]
    )
    toc_like_entries = 0

    for line in lines:
        has_page_number = bool(re.search(r"(?:\.{2,}|\s)\s*\d{1,4}$", line))
        looks_like_section = bool(re.match(r"^\d+(?:\.\d+)?\s*[A-Za-z]", line))
        if has_page_number and (looks_like_section or len(line) >= 15):
            toc_like_entries += 1

    if has_contents_header and toc_like_entries >= 2:
        return "yes"
    if "table of contents" in joined and toc_like_entries >= 1:
        return "yes"
    return None


def _normalize_toc_line(line: str | None) -> str:
    if not line:
        return ""
    normalized = re.sub(r"\s+", " ", str(line)).strip()
    normalized = normalized.strip("-*• ")
    return normalized


def _parse_toc_line_heuristically(raw_line: str):
    line = _normalize_toc_line(raw_line)
    if not line:
        return None
    if line.lower() in TOC_IGNORED_LINES:
        return None
    if "| page " in line.lower():
        return None
    if re.search(r"\bpage\s+\d+\s*/\s*\d+\b", line, re.IGNORECASE):
        return None
    if len(line) < 4 or len(line) > 220:
        return None
    if not re.search(r"[A-Za-z]", line):
        return None

    page_match = re.match(r"^(?P<body>.+?)(?:\s*:\s*|\s+)(?P<page>\d{1,4})$", line)
    if not page_match:
        return None

    body = page_match.group("body").strip(" :-")
    page = int(page_match.group("page"))
    if not body:
        return None

    structure = None
    title = body

    structure_match = re.match(r"^(?P<structure>\d+(?:\.\d+)*|[A-Z])[\.\)]\s+(?P<title>.+)$", body)
    if structure_match:
        structure = structure_match.group("structure")
        title = structure_match.group("title").strip()
    else:
        numeric_prefix_match = re.match(r"^(?P<structure>\d+(?:\.\d+)*)\s+(?P<title>.+)$", body)
        if numeric_prefix_match:
            structure = numeric_prefix_match.group("structure")
            title = numeric_prefix_match.group("title").strip()

    if not title or title.lower() in TOC_IGNORED_LINES:
        return None

    return {
        "structure": structure,
        "title": title,
        "page": page,
    }


def _canonicalize_generated_title(title: str | None) -> str:
    title = _normalize_toc_line(title)
    title = re.sub(r"^section\s+\d+(?:\.\d+)*\s*:\s*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^[A-Z]?\d+(?:\.\d+)*\s+", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title.lower()


def _is_generic_generated_title(title: str | None) -> bool:
    canonical = _canonicalize_generated_title(title)
    return canonical in GENERIC_TOC_TITLES


def _specificity_score(title: str | None, parent_title: str | None = None) -> int:
    original = _normalize_toc_line(title)
    canonical = _canonicalize_generated_title(title)
    score = 0

    if not original:
        return -1000

    if parent_title and canonical == _canonicalize_generated_title(parent_title):
        score -= 80

    if _is_generic_generated_title(original):
        score -= 40

    if re.search(r"\b(table|figure|appendix|exhibit|chart)\b", original, re.IGNORECASE):
        score += 100
    if re.match(r"^[A-Z]?\d+(?:\.\d+)*\s+", original):
        score += 20
    if len(original.split()) >= 5:
        score += 20
    if re.search(r"[,:;-]", original):
        score += 5

    return score


def _post_process_generated_toc_items(items, parent_title: str | None = None):
    if not items:
        return []

    cleaned = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _normalize_toc_line(item.get("title"))
        if not title:
            continue
        candidate = copy.deepcopy(item)
        candidate["title"] = title
        physical_index = convert_physical_index_to_int(candidate.get("physical_index"))
        candidate["physical_index"] = physical_index
        dedupe_key = (physical_index, _canonicalize_generated_title(title))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        cleaned.append(candidate)

    grouped = defaultdict(list)
    for item in cleaned:
        grouped[item.get("physical_index")].append(item)

    filtered = []
    def _group_sort_key(value):
        if value is None:
            return (1, 0)
        if isinstance(value, int):
            return (0, value)
        normalized = convert_physical_index_to_int(value)
        if normalized is None:
            return (1, 0)
        return (0, normalized)

    for physical_index in sorted(grouped, key=_group_sort_key):
        group = grouped[physical_index]
        scores = {id(item): _specificity_score(item.get("title"), parent_title=parent_title) for item in group}
        best_score = max(scores.values())
        has_strong_specific = best_score >= 60

        for idx, item in enumerate(group):
            score = scores[id(item)]
            title = item.get("title")
            canonical_title = _canonicalize_generated_title(title)
            parent_canonical = _canonicalize_generated_title(parent_title) if parent_title else None
            if has_strong_specific and _is_generic_generated_title(title) and score < best_score:
                continue
            if parent_canonical and canonical_title == parent_canonical and has_strong_specific:
                continue
            if idx > 0 and parent_canonical and canonical_title == parent_canonical:
                continue
            filtered.append(item)

    if not filtered:
        return []

    merged = []
    last_seen_page_by_title = {}
    for item in filtered:
        current = copy.deepcopy(item)
        current_title = _canonicalize_generated_title(current.get("title"))
        current_page = current.get("physical_index")
        last_seen_page = last_seen_page_by_title.get(current_title)

        if (
            current_title
            and isinstance(current_page, int)
            and isinstance(last_seen_page, int)
            and current_page == last_seen_page + 1
        ):
            last_seen_page_by_title[current_title] = current_page
            continue

        merged.append(current)
        if current_title and isinstance(current_page, int):
            last_seen_page_by_title[current_title] = current_page

    return merged


def _toc_transformer_heuristic(toc_content):
    lines = [_normalize_toc_line(line) for line in str(toc_content).splitlines()]
    parsed_entries = []
    seen = set()

    for line in lines:
        entry = _parse_toc_line_heuristically(line)
        if not entry:
            continue
        dedupe_key = (entry["structure"], entry["title"].lower(), entry["page"])
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        parsed_entries.append(entry)

    if len(parsed_entries) >= 3:
        return parsed_entries
    return None


def _split_toc_content_for_parallel_transform(toc_content, max_lines_per_chunk=24, max_chars=3500):
    raw_lines = [_normalize_toc_line(line) for line in str(toc_content).splitlines()]
    lines = [line for line in raw_lines if line]
    if not lines:
        return []

    chunks = []
    current_lines = []
    current_chars = 0
    for line in lines:
        projected_chars = current_chars + len(line) + 1
        if current_lines and (len(current_lines) >= max_lines_per_chunk or projected_chars > max_chars):
            chunks.append("\n".join(current_lines))
            current_lines = [line]
            current_chars = len(line)
        else:
            current_lines.append(line)
            current_chars = projected_chars
    if current_lines:
        chunks.append("\n".join(current_lines))
    return chunks


def _toc_transform_chunk(chunk_content, model=None):
    prompt = f"""
    You are given a PARTIAL table of contents from a document.
    Transform only the provided entries into a JSON array.

    Return JSON only in this format:
    [
      {{
        "structure": "<x.x or null>",
        "title": "<section title>",
        "page": <page number or null>
      }}
    ]

    Rules:
    - Only output entries that are present in the partial table of contents.
    - Do not invent entries.
    - Keep titles concise and faithful to the source.
    - If there is no visible hierarchy index, use null.
    - If there is no visible page number, use null.

    Partial table of contents:
    {chunk_content}
    """

    response = llm_completion(model=model, prompt=prompt, debug_label="toc_transform_chunk")
    parsed = extract_json(response, debug_label="toc_transform_chunk")
    return parsed if isinstance(parsed, list) else []


def _toc_transformer_parallel(toc_content, model=None, max_workers=4, logger=None):
    chunks = _split_toc_content_for_parallel_transform(toc_content)
    if len(chunks) <= 1:
        _stage_log("toc_transformer", "parallel path skipped", logger=logger, reason="single_chunk")
        return None

    _stage_log("toc_transformer", "parallel path started", logger=logger, chunks=len(chunks), workers=min(max_workers, len(chunks)))
    results = {}
    start_time = time.perf_counter()
    with ThreadPoolExecutor(max_workers=min(max_workers, len(chunks))) as executor:
        future_map = {
            executor.submit(_toc_transform_chunk, chunk, model): idx
            for idx, chunk in enumerate(chunks)
        }
        for future in as_completed(future_map):
            idx = future_map[future]
            try:
                results[idx] = future.result()
            except Exception:
                _stage_log("toc_transformer", "parallel path failed", logger=logger, chunk_index=idx)
                return None

    merged = []
    seen = set()
    for idx in range(len(chunks)):
        for item in results.get(idx, []):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            page = item.get("page")
            structure = item.get("structure")
            dedupe_key = (structure, title.lower(), page)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            merged.append({
                "structure": structure,
                "title": title,
                "page": page,
            })

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    if len(merged) >= 3:
        _stage_log("toc_transformer", "parallel path completed", logger=logger, entries=len(merged), duration_ms=duration_ms)
        return merged

    _stage_log("toc_transformer", "parallel path produced insufficient entries", logger=logger, entries=len(merged), duration_ms=duration_ms)
    return None


################### check title in page #########################################################
async def check_title_appearance(item, page_list, start_index=1, model=None):    
    title=item['title']
    if 'physical_index' not in item or item['physical_index'] is None:
        return {'list_index': item.get('list_index'), 'answer': 'no', 'title':title, 'page_number': None}
    
    
    page_number = item['physical_index']
    page_text = page_list[page_number-start_index][0]
    _stage_log(
        "check_title_appearance",
        "request",
        title=title,
        page_number=page_number,
        page_text_chars=len(page_text or ""),
    )

    
    prompt = f"""
    Your job is to check if the given section appears or starts in the given page_text.

    Note: do fuzzy matching, ignore any space inconsistency in the page_text.

    The given section title is {title}.
    The given page_text is {page_text}.
    
    Reply format:
    {{
        
        "thinking": <why do you think the section appears or starts in the page_text>
        "answer": "yes or no" (yes if the section appears or starts in the page_text, no otherwise)
    }}
    Directly return the final JSON structure. Do not output anything else."""

    response = await llm_acompletion(model=model, prompt=prompt, debug_label="check_title_appearance")
    _stage_log(
        "check_title_appearance",
        "response_received",
        title=title,
        page_number=page_number,
        response_chars=len(response or ""),
    )
    response = extract_json(response, debug_label="check_title_appearance")
    _stage_log(
        "check_title_appearance",
        "response_parsed",
        title=title,
        page_number=page_number,
        parsed_keys=",".join(sorted(response.keys())) if isinstance(response, dict) else "non_dict",
    )
    if 'answer' in response:
        answer = response['answer']
    else:
        answer = 'no'
    return {'list_index': item['list_index'], 'answer': answer, 'title': title, 'page_number': page_number}


async def check_title_appearance_in_start(title, page_text, model=None, logger=None):    
    prompt = f"""
    You will be given the current section title and the current page_text.
    Your job is to check if the current section starts in the beginning of the given page_text.
    If there are other contents before the current section title, then the current section does not start in the beginning of the given page_text.
    If the current section title is the first content in the given page_text, then the current section starts in the beginning of the given page_text.

    Note: do fuzzy matching, ignore any space inconsistency in the page_text.

    The given section title is {title}.
    The given page_text is {page_text}.
    
    reply format:
    {{
        "thinking": <why do you think the section appears or starts in the page_text>
        "start_begin": "yes or no" (yes if the section starts in the beginning of the page_text, no otherwise)
    }}
    Directly return the final JSON structure. Do not output anything else."""

    response = await llm_acompletion(model=model, prompt=prompt, debug_label="check_title_appearance_in_start")
    response = extract_json(response, debug_label="check_title_appearance_in_start")
    if logger:
        logger.info(f"Response: {response}")
    return response.get("start_begin", "no")


async def check_title_appearance_in_start_concurrent(structure, page_list, model=None, logger=None):
    if logger:
        logger.info("Checking title appearance in start concurrently")
    
    # skip items without physical_index
    for item in structure:
        if item.get('physical_index') is None:
            item['appear_start'] = 'no'

    # only for items with valid physical_index
    tasks = []
    valid_items = []
    for item in structure:
        if item.get('physical_index') is not None:
            page_text = page_list[item['physical_index'] - 1][0]
            tasks.append(check_title_appearance_in_start(item['title'], page_text, model=model, logger=logger))
            valid_items.append(item)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    flush_litellm_logging_worker_sync(timeout_seconds=2.0)
    for item, result in zip(valid_items, results):
        if isinstance(result, Exception):
            if logger:
                logger.error(f"Error checking start for {item['title']}: {result}")
            item['appear_start'] = 'no'
        else:
            item['appear_start'] = result

    return structure


def toc_detector_single_page(content, model=None):
    heuristic_result = _heuristic_toc_detect(content)
    if heuristic_result is not None:
        return heuristic_result

    prompt = f"""
    Your job is to detect if there is a table of content provided in the given text.

    Given text: {content}

    return the following JSON format:
    {{
        "thinking": <why do you think there is a table of content in the given text>
        "toc_detected": "<yes or no>",
    }}

    Directly return the final JSON structure. Do not output anything else.
    Please note: abstract,summary, notation list, figure list, table list, etc. are not table of contents."""

    response = llm_completion(model=model, prompt=prompt, debug_label="toc_detector_single_page")
    # print('response', response)
    json_content = extract_json(response, debug_label="toc_detector_single_page")
    detected = json_content.get('toc_detected') if isinstance(json_content, dict) else None
    if detected in {'yes', 'no'}:
        return detected

    logging.warning("toc_detector_single_page: invalid or empty model response, falling back to 'no'")
    return 'no'


def check_if_toc_extraction_is_complete(content, toc, model=None):
    prompt = f"""
    You are given a partial document  and a  table of contents.
    Your job is to check if the  table of contents is complete, which it contains all the main sections in the partial document.

    Reply format:
    {{
        "thinking": <why do you think the table of contents is complete or not>
        "completed": "yes" or "no"
    }}
    Directly return the final JSON structure. Do not output anything else."""

    prompt = prompt + '\n Document:\n' + content + '\n Table of contents:\n' + toc
    response = llm_completion(model=model, prompt=prompt, debug_label="check_if_toc_extraction_is_complete")
    json_content = extract_json(response, debug_label="check_if_toc_extraction_is_complete")
    return json_content['completed']


def check_if_toc_transformation_is_complete(content, toc, model=None):
    prompt = f"""
    You are given a raw table of contents and a  table of contents.
    Your job is to check if the  table of contents is complete.

    Reply format:
    {{
        "thinking": <why do you think the cleaned table of contents is complete or not>
        "completed": "yes" or "no"
    }}
    Directly return the final JSON structure. Do not output anything else."""

    prompt = prompt + '\n Raw Table of contents:\n' + content + '\n Cleaned Table of contents:\n' + toc
    response = llm_completion(model=model, prompt=prompt, debug_label="check_if_toc_transformation_is_complete")
    json_content = extract_json(response, debug_label="check_if_toc_transformation_is_complete")
    return json_content['completed']

def extract_toc_content(content, model=None):
    prompt = f"""
    Your job is to extract the full table of contents from the given text, replace ... with :

    Given text: {content}

    Directly return the full table of contents content. Do not output anything else."""

    response, finish_reason = llm_completion(model=model, prompt=prompt, return_finish_reason=True, debug_label="extract_toc_content:init")
    
    if_complete = check_if_toc_transformation_is_complete(content, response, model)
    if if_complete == "yes" and finish_reason == "finished":
        return response
    
    chat_history = [
        {"role": "user", "content": prompt}, 
        {"role": "assistant", "content": response},    
    ]
    prompt = f"""please continue the generation of table of contents , directly output the remaining part of the structure"""
    new_response, finish_reason = llm_completion(model=model, prompt=prompt, chat_history=chat_history, return_finish_reason=True, debug_label="extract_toc_content:continue")
    response = response + new_response
    if_complete = check_if_toc_transformation_is_complete(content, response, model)
    
    attempt = 0
    max_attempts = 5

    while not (if_complete == "yes" and finish_reason == "finished"):
        attempt += 1
        if attempt > max_attempts:
            raise Exception('Failed to complete table of contents after maximum retries')

        chat_history = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response},
        ]
        prompt = f"""please continue the generation of table of contents , directly output the remaining part of the structure"""
        new_response, finish_reason = llm_completion(model=model, prompt=prompt, chat_history=chat_history, return_finish_reason=True, debug_label="extract_toc_content:retry")
        response = response + new_response
        if_complete = check_if_toc_transformation_is_complete(content, response, model)
    
    return response

def detect_page_index(toc_content, model=None):
    print('start detect_page_index')
    prompt = f"""
    You will be given a table of contents.

    Your job is to detect if there are page numbers/indices given within the table of contents.

    Given text: {toc_content}

    Reply format:
    {{
        "thinking": <why do you think there are page numbers/indices given within the table of contents>
        "page_index_given_in_toc": "<yes or no>"
    }}
    Directly return the final JSON structure. Do not output anything else."""

    response = llm_completion(model=model, prompt=prompt, debug_label="detect_page_index")
    json_content = extract_json(response, debug_label="detect_page_index")
    return json_content['page_index_given_in_toc']

def toc_extractor(page_list, toc_page_list, model):
    def transform_dots_to_colon(text):
        text = re.sub(r'\.{5,}', ': ', text)
        # Handle dots separated by spaces
        text = re.sub(r'(?:\. ){5,}\.?', ': ', text)
        return text
    
    toc_content = ""
    for page_index in toc_page_list:
        toc_content += page_list[page_index][0]
    toc_content = transform_dots_to_colon(toc_content)
    has_page_index = detect_page_index(toc_content, model=model)
    
    return {
        "toc_content": toc_content,
        "page_index_given_in_toc": has_page_index
    }




def toc_index_extractor(toc, content, model=None):
    print('start toc_index_extractor')
    toc_extractor_prompt = """
    You are given a table of contents in a json format and several pages of a document, your job is to add the physical_index to the table of contents in the json format.

    The provided pages contains tags like <physical_index_X> and <physical_index_X> to indicate the physical location of the page X.

    The structure variable is the numeric system which represents the index of the hierarchy section in the table of contents. For example, the first section has structure index 1, the first subsection has structure index 1.1, the second subsection has structure index 1.2, etc.

    The response should be in the following JSON format: 
    [
        {
            "structure": <structure index, "x.x.x" or None> (string),
            "title": <title of the section>,
            "physical_index": "<physical_index_X>" (keep the format)
        },
        ...
    ]

    Only add the physical_index to the sections that are in the provided pages.
    If the section is not in the provided pages, do not add the physical_index to it.
    Directly return the final JSON structure. Do not output anything else."""

    prompt = toc_extractor_prompt + '\nTable of contents:\n' + str(toc) + '\nDocument pages:\n' + content
    response = llm_completion(model=model, prompt=prompt, debug_label="toc_index_extractor")
    json_content = extract_json(response, debug_label="toc_index_extractor")    
    return json_content



def _toc_transformer_sequential(toc_content, model=None, logger=None):
    _stage_log("toc_transformer", "sequential path started", logger=logger)
    start_time = time.perf_counter()
    init_prompt = """
    You are given a table of contents, You job is to transform the whole table of content into a JSON format included table_of_contents.

    structure is the numeric system which represents the index of the hierarchy section in the table of contents. For example, the first section has structure index 1, the first subsection has structure index 1.1, the second subsection has structure index 1.2, etc.

    The response should be in the following JSON format: 
    {
    table_of_contents: [
        {
            "structure": <structure index, "x.x.x" or None> (string),
            "title": <title of the section>,
            "page": <page number or None>,
        },
        ...
        ],
    }
    You should transform the full table of contents in one go.
    Directly return the final JSON structure, do not output anything else. """

    prompt = init_prompt + '\n Given table of contents\n:' + toc_content
    last_complete, finish_reason = llm_completion(model=model, prompt=prompt, return_finish_reason=True, debug_label="toc_transformer_sequential:init")
    if_complete = check_if_toc_transformation_is_complete(toc_content, last_complete, model)
    if if_complete == "yes" and finish_reason == "finished":
        last_complete = extract_json(last_complete, debug_label="toc_transformer_sequential:init")
        cleaned_response=convert_page_to_int(last_complete['table_of_contents'])
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        _stage_log("toc_transformer", "sequential path completed", logger=logger, entries=len(cleaned_response), duration_ms=duration_ms)
        return cleaned_response
    
    last_complete = get_json_content(last_complete)
    attempt = 0
    max_attempts = 5
    while not (if_complete == "yes" and finish_reason == "finished"):
        attempt += 1
        if attempt > max_attempts:
            raise Exception('Failed to complete toc transformation after maximum retries')
        position = last_complete.rfind('}')
        if position != -1:
            last_complete = last_complete[:position+2]
        prompt = f"""
        Your task is to continue the table of contents json structure, directly output the remaining part of the json structure.
        The response should be in the following JSON format: 

        The raw table of contents json structure is:
        {toc_content}

        The incomplete transformed table of contents json structure is:
        {last_complete}

        Please continue the json structure, directly output the remaining part of the json structure."""

        new_complete, finish_reason = llm_completion(model=model, prompt=prompt, return_finish_reason=True, debug_label="toc_transformer_sequential:continue")

        if new_complete.startswith('```json'):
            new_complete =  get_json_content(new_complete)
            last_complete = last_complete+new_complete

        if_complete = check_if_toc_transformation_is_complete(toc_content, last_complete, model)
        

    last_complete = json.loads(last_complete)

    cleaned_response=convert_page_to_int(last_complete['table_of_contents'])
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    _stage_log("toc_transformer", "sequential path completed", logger=logger, entries=len(cleaned_response), duration_ms=duration_ms)
    return cleaned_response


def toc_transformer(toc_content, model=None, logger=None):
    _stage_log("toc_transformer", "started", logger=logger)
    start_time = time.perf_counter()

    heuristic_result = _toc_transformer_heuristic(toc_content)
    if heuristic_result:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        _stage_log("toc_transformer", "heuristic path completed", logger=logger, entries=len(heuristic_result), duration_ms=duration_ms)
        return convert_page_to_int(heuristic_result)

    _stage_log("toc_transformer", "heuristic path skipped", logger=logger, reason="insufficient_entries")
    parallel_result = _toc_transformer_parallel(toc_content, model=model, logger=logger)
    if parallel_result:
        return convert_page_to_int(parallel_result)

    _stage_log("toc_transformer", "falling back to sequential path", logger=logger)
    return _toc_transformer_sequential(toc_content, model=model, logger=logger)
    



def find_toc_pages(start_page_index, page_list, opt, logger=None):
    print('start find_toc_pages')
    last_page_is_yes = False
    toc_page_list = []
    i = start_page_index
    
    while i < len(page_list):
        # Only check beyond max_pages if we're still finding TOC pages
        if i >= opt.toc_check_page_num and not last_page_is_yes:
            break
        detected_result = toc_detector_single_page(page_list[i][0],model=opt.model)
        if detected_result == 'yes':
            if logger:
                logger.info(f'Page {i} has toc')
            toc_page_list.append(i)
            last_page_is_yes = True
        elif detected_result == 'no' and last_page_is_yes:
            if logger:
                logger.info(f'Found the last page with toc: {i-1}')
            break
        i += 1
    
    if not toc_page_list and logger:
        logger.info('No toc found')
        
    return toc_page_list

def remove_page_number(data):
    if isinstance(data, dict):
        data.pop('page_number', None)  
        for key in list(data.keys()):
            if 'nodes' in key:
                remove_page_number(data[key])
    elif isinstance(data, list):
        for item in data:
            remove_page_number(item)
    return data

def extract_matching_page_pairs(toc_page, toc_physical_index, start_page_index):
    pairs = []
    for phy_item in toc_physical_index:
        for page_item in toc_page:
            if phy_item.get('title') == page_item.get('title'):
                physical_index = phy_item.get('physical_index')
                if physical_index is not None and int(physical_index) >= start_page_index:
                    pairs.append({
                        'title': phy_item.get('title'),
                        'page': page_item.get('page'),
                        'physical_index': physical_index
                    })
    return pairs


def calculate_page_offset(pairs):
    differences = []
    for pair in pairs:
        try:
            physical_index = pair['physical_index']
            page_number = pair['page']
            difference = physical_index - page_number
            differences.append(difference)
        except (KeyError, TypeError):
            continue
    
    if not differences:
        return None
    
    difference_counts = {}
    for diff in differences:
        difference_counts[diff] = difference_counts.get(diff, 0) + 1
    
    most_common = max(difference_counts.items(), key=lambda x: x[1])[0]
    
    return most_common

def add_page_offset_to_toc_json(data, offset):
    for i in range(len(data)):
        if data[i].get('page') is not None and isinstance(data[i]['page'], int):
            data[i]['physical_index'] = data[i]['page'] + offset
            del data[i]['page']
    
    return data



def page_list_to_group_text(page_contents, token_lengths, max_tokens=20000, overlap_page=1):    
    num_tokens = sum(token_lengths)
    
    if num_tokens <= max_tokens:
        # merge all pages into one text
        page_text = "".join(page_contents)
        return [page_text]
    
    subsets = []
    current_subset = []
    current_token_count = 0

    expected_parts_num = math.ceil(num_tokens / max_tokens)
    average_tokens_per_part = math.ceil(((num_tokens / expected_parts_num) + max_tokens) / 2)
    
    for i, (page_content, page_tokens) in enumerate(zip(page_contents, token_lengths)):
        if current_token_count + page_tokens > average_tokens_per_part:

            subsets.append(''.join(current_subset))
            # Start new subset from overlap if specified
            overlap_start = max(i - overlap_page, 0)
            current_subset = page_contents[overlap_start:i]
            current_token_count = sum(token_lengths[overlap_start:i])
        
        # Add current page to the subset
        current_subset.append(page_content)
        current_token_count += page_tokens

    # Add the last subset if it contains any pages
    if current_subset:
        subsets.append(''.join(current_subset))
    
    print('divide page_list to groups', len(subsets))
    return subsets

def add_page_number_to_toc(part, structure, model=None):
    fill_prompt_seq = """
    You are given an JSON structure of a document and a partial part of the document. Your task is to check if the title that is described in the structure is started in the partial given document.

    The provided text contains tags like <physical_index_X> and <physical_index_X> to indicate the physical location of the page X. 

    If the full target section starts in the partial given document, insert the given JSON structure with the "start": "yes", and "start_index": "<physical_index_X>".

    If the full target section does not start in the partial given document, insert "start": "no",  "start_index": None.

    The response should be in the following format. 
        [
            {
                "structure": <structure index, "x.x.x" or None> (string),
                "title": <title of the section>,
                "start": "<yes or no>",
                "physical_index": "<physical_index_X> (keep the format)" or None
            },
            ...
        ]    
    The given structure contains the result of the previous part, you need to fill the result of the current part, do not change the previous result.
    Directly return the final JSON structure. Do not output anything else."""

    prompt = fill_prompt_seq + f"\n\nCurrent Partial Document:\n{part}\n\nGiven Structure\n{json.dumps(structure, indent=2)}\n"
    current_json_raw = llm_completion(model=model, prompt=prompt, debug_label="add_page_number_to_toc")
    json_result = extract_json(current_json_raw, debug_label="add_page_number_to_toc")
    
    for item in json_result:
        if 'start' in item:
            del item['start']
    return json_result


def remove_first_physical_index_section(text):
    """
    Removes the first section between <physical_index_X> and <physical_index_X> tags,
    and returns the remaining text.
    """
    pattern = r'<physical_index_\d+>.*?<physical_index_\d+>'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        # Remove the first matched section
        return text.replace(match.group(0), '', 1)
    return text

### add verify completeness
def generate_toc_continue(toc_content, part, model=None):
    print('start generate_toc_continue')
    prompt = """
    You are an expert in extracting hierarchical tree structure.
    You are given a tree structure of the previous part and the text of the current part.
    Your task is to continue the tree structure from the previous part to include the current part.

    The structure variable is the numeric system which represents the index of the hierarchy section in the table of contents. For example, the first section has structure index 1, the first subsection has structure index 1.1, the second subsection has structure index 1.2, etc.

    For the title, you need to extract the original title from the text, only fix the space inconsistency.

    Prefer the MOST SPECIFIC visible heading on a page.
    If both a generic subsection label and a more specific heading exist on the same page, keep the more specific one.
    Examples of generic subsection labels to avoid when a more specific title exists:
    - Overview
    - Background
    - Design Goals
    - Implementation Details
    - Testing Notes
    - Detailed Findings
    - Summary
    - Conclusion

    Prefer specific table / figure / appendix titles such as:
    - Table R.1. ...
    - Figure 2. ...
    - Appendix A ...

    Do not include page headers, page footers, or document title lines such as:
    - <document name> | Page X / Y

    The provided text contains tags like <physical_index_X> and <physical_index_X> to indicate the start and end of page X. \
    
    For the physical_index, you need to extract the physical index of the start of the section from the text. Keep the <physical_index_X> format.

    The response should be in the following format. 
        [
            {
                "structure": <structure index, "x.x.x"> (string),
                "title": <title of the section, keep the original title>,
                "physical_index": "<physical_index_X> (keep the format)"
            },
            ...
        ]    

    Directly return the additional part of the final JSON structure. Do not output anything else."""

    prompt = prompt + '\nGiven text\n:' + part + '\nPrevious tree structure\n:' + json.dumps(toc_content, indent=2)
    response, finish_reason = llm_completion(model=model, prompt=prompt, return_finish_reason=True, debug_label="generate_toc_continue")
    if finish_reason == 'finished':
        parsed = extract_json(response, debug_label="generate_toc_continue")
        return _post_process_generated_toc_items(parsed)
    else:
        raise Exception(f'finish reason: {finish_reason}')
    
### add verify completeness
def generate_toc_init(part, model=None):
    print('start generate_toc_init')
    prompt = """
    You are an expert in extracting hierarchical tree structure, your task is to generate the tree structure of the document.

    The structure variable is the numeric system which represents the index of the hierarchy section in the table of contents. For example, the first section has structure index 1, the first subsection has structure index 1.1, the second subsection has structure index 1.2, etc.

    For the title, you need to extract the original title from the text, only fix the space inconsistency.

    Prefer the MOST SPECIFIC visible heading on a page.
    If both a generic subsection label and a more specific heading exist on the same page, keep the more specific one.
    Examples of generic subsection labels to avoid when a more specific title exists:
    - Overview
    - Background
    - Design Goals
    - Implementation Details
    - Testing Notes
    - Detailed Findings
    - Summary
    - Conclusion

    Prefer specific table / figure / appendix titles such as:
    - Table R.1. ...
    - Figure 2. ...
    - Appendix A ...

    Do not include page headers, page footers, or document title lines such as:
    - <document name> | Page X / Y

    The provided text contains tags like <physical_index_X> and <physical_index_X> to indicate the start and end of page X. 

    For the physical_index, you need to extract the physical index of the start of the section from the text. Keep the <physical_index_X> format.

    The response should be in the following format. 
        [
            {{
                "structure": <structure index, "x.x.x"> (string),
                "title": <title of the section, keep the original title>,
                "physical_index": "<physical_index_X> (keep the format)"
            }},
            
        ],


    Directly return the final JSON structure. Do not output anything else."""

    prompt = prompt + '\nGiven text\n:' + part
    response, finish_reason = llm_completion(model=model, prompt=prompt, return_finish_reason=True, debug_label="generate_toc_init")

    if finish_reason == 'finished':
         parsed = extract_json(response, debug_label="generate_toc_init")
         return _post_process_generated_toc_items(parsed)
    else:
        raise Exception(f'finish reason: {finish_reason}')

def process_no_toc(page_list, start_index=1, model=None, logger=None):
    page_contents=[]
    token_lengths=[]
    for page_index in range(start_index, start_index+len(page_list)):
        page_text = f"<physical_index_{page_index}>\n{page_list[page_index-start_index][0]}\n<physical_index_{page_index}>\n\n"
        page_contents.append(page_text)
        token_lengths.append(count_tokens(page_text, model))
    group_texts = page_list_to_group_text(page_contents, token_lengths)
    logger.info(f'len(group_texts): {len(group_texts)}')

    toc_with_page_number= generate_toc_init(group_texts[0], model)
    for group_text in group_texts[1:]:
        toc_with_page_number_additional = generate_toc_continue(toc_with_page_number, group_text, model)    
        toc_with_page_number.extend(toc_with_page_number_additional)
    toc_with_page_number = _post_process_generated_toc_items(toc_with_page_number)
    title_counts = {}
    for item in toc_with_page_number:
        title = str(item.get("title") or "").strip()
        if title:
            title_counts[title] = title_counts.get(title, 0) + 1
    repeated_titles = {title: count for title, count in title_counts.items() if count > 1}
    _stage_log(
        "process_no_toc",
        "generated_toc_summary",
        logger=logger,
        entries=len(toc_with_page_number),
        repeated_titles=len(repeated_titles),
        sample_titles=" | ".join(list(title_counts.keys())[:5]),
    )
    logger.info(f'generate_toc: {toc_with_page_number}')

    toc_with_page_number = convert_physical_index_to_int(toc_with_page_number)
    logger.info(f'convert_physical_index_to_int: {toc_with_page_number}')

    return toc_with_page_number

def process_toc_no_page_numbers(toc_content, toc_page_list, page_list,  start_index=1, model=None, logger=None):
    page_contents=[]
    token_lengths=[]
    stage_start = time.perf_counter()
    toc_content = toc_transformer(toc_content, model, logger=logger)
    logger.info(f'toc_transformer: {toc_content}')
    for page_index in range(start_index, start_index+len(page_list)):
        page_text = f"<physical_index_{page_index}>\n{page_list[page_index-start_index][0]}\n<physical_index_{page_index}>\n\n"
        page_contents.append(page_text)
        token_lengths.append(count_tokens(page_text, model))
    
    group_texts = page_list_to_group_text(page_contents, token_lengths)
    logger.info(f'len(group_texts): {len(group_texts)}')

    toc_with_page_number=copy.deepcopy(toc_content)
    for group_text in group_texts:
        toc_with_page_number = add_page_number_to_toc(group_text, toc_with_page_number, model)
    logger.info(f'add_page_number_to_toc: {toc_with_page_number}')

    toc_with_page_number = convert_physical_index_to_int(toc_with_page_number)
    logger.info(f'convert_physical_index_to_int: {toc_with_page_number}')
    _stage_log(
        "process_toc_no_page_numbers",
        "completed",
        logger=logger,
        entries=len(toc_with_page_number),
        duration_ms=round((time.perf_counter() - stage_start) * 1000, 2),
    )

    return toc_with_page_number



def process_toc_with_page_numbers(toc_content, toc_page_list, page_list, toc_check_page_num=None, model=None, logger=None):
    stage_start = time.perf_counter()
    toc_with_page_number = toc_transformer(toc_content, model, logger=logger)
    logger.info(f'toc_with_page_number: {toc_with_page_number}')

    toc_no_page_number = remove_page_number(copy.deepcopy(toc_with_page_number))
    
    start_page_index = toc_page_list[-1] + 1
    main_content = ""
    for page_index in range(start_page_index, min(start_page_index + toc_check_page_num, len(page_list))):
        main_content += f"<physical_index_{page_index+1}>\n{page_list[page_index][0]}\n<physical_index_{page_index+1}>\n\n"

    toc_with_physical_index = toc_index_extractor(toc_no_page_number, main_content, model)
    logger.info(f'toc_with_physical_index: {toc_with_physical_index}')

    toc_with_physical_index = convert_physical_index_to_int(toc_with_physical_index)
    logger.info(f'toc_with_physical_index: {toc_with_physical_index}')

    matching_pairs = extract_matching_page_pairs(toc_with_page_number, toc_with_physical_index, start_page_index)
    logger.info(f'matching_pairs: {matching_pairs}')

    offset = calculate_page_offset(matching_pairs)
    logger.info(f'offset: {offset}')

    toc_with_page_number = add_page_offset_to_toc_json(toc_with_page_number, offset)
    logger.info(f'toc_with_page_number: {toc_with_page_number}')

    toc_with_page_number = process_none_page_numbers(toc_with_page_number, page_list, model=model)
    logger.info(f'toc_with_page_number: {toc_with_page_number}')
    _stage_log(
        "process_toc_with_page_numbers",
        "completed",
        logger=logger,
        toc_entries=len(toc_with_page_number),
        matching_pairs=len(matching_pairs),
        duration_ms=round((time.perf_counter() - stage_start) * 1000, 2),
    )

    return toc_with_page_number



##check if needed to process none page numbers
def process_none_page_numbers(toc_items, page_list, start_index=1, model=None):
    for i, item in enumerate(toc_items):
        if "physical_index" not in item:
            # logger.info(f"fix item: {item}")
            # Find previous physical_index
            prev_physical_index = 0  # Default if no previous item exists
            for j in range(i - 1, -1, -1):
                if toc_items[j].get('physical_index') is not None:
                    prev_physical_index = toc_items[j]['physical_index']
                    break
            
            # Find next physical_index
            next_physical_index = -1  # Default if no next item exists
            for j in range(i + 1, len(toc_items)):
                if toc_items[j].get('physical_index') is not None:
                    next_physical_index = toc_items[j]['physical_index']
                    break

            page_contents = []
            for page_index in range(prev_physical_index, next_physical_index+1):
                # Add bounds checking to prevent IndexError
                list_index = page_index - start_index
                if list_index >= 0 and list_index < len(page_list):
                    page_text = f"<physical_index_{page_index}>\n{page_list[list_index][0]}\n<physical_index_{page_index}>\n\n"
                    page_contents.append(page_text)
                else:
                    continue

            item_copy = copy.deepcopy(item)
            del item_copy['page']
            result = add_page_number_to_toc(page_contents, item_copy, model)
            if isinstance(result[0]['physical_index'], str) and result[0]['physical_index'].startswith('<physical_index'):
                item['physical_index'] = int(result[0]['physical_index'].split('_')[-1].rstrip('>').strip())
                del item['page']
    
    return toc_items




def check_toc(page_list, opt=None):
    toc_page_list = find_toc_pages(start_page_index=0, page_list=page_list, opt=opt)
    if len(toc_page_list) == 0:
        print('no toc found')
        _stage_log("check_toc", "completed", toc_pages=0, mode="no_toc")
        return {'toc_content': None, 'toc_page_list': [], 'page_index_given_in_toc': 'no'}
    else:
        print('toc found')
        _stage_log("check_toc", "toc_pages_detected", toc_pages=len(toc_page_list), first_page=toc_page_list[0], last_page=toc_page_list[-1])
        toc_json = toc_extractor(page_list, toc_page_list, opt.model)

        if toc_json['page_index_given_in_toc'] == 'yes':
            print('index found')
            _stage_log("check_toc", "completed", toc_pages=len(toc_page_list), mode="toc_with_page_numbers")
            return {'toc_content': toc_json['toc_content'], 'toc_page_list': toc_page_list, 'page_index_given_in_toc': 'yes'}
        else:
            current_start_index = toc_page_list[-1] + 1
            
            while (toc_json['page_index_given_in_toc'] == 'no' and 
                   current_start_index < len(page_list) and 
                   current_start_index < opt.toc_check_page_num):
                
                additional_toc_pages = find_toc_pages(
                    start_page_index=current_start_index,
                    page_list=page_list,
                    opt=opt
                )
                
                if len(additional_toc_pages) == 0:
                    break

                additional_toc_json = toc_extractor(page_list, additional_toc_pages, opt.model)
                if additional_toc_json['page_index_given_in_toc'] == 'yes':
                    print('index found')
                    _stage_log("check_toc", "completed", toc_pages=len(additional_toc_pages), mode="additional_toc_with_page_numbers")
                    return {'toc_content': additional_toc_json['toc_content'], 'toc_page_list': additional_toc_pages, 'page_index_given_in_toc': 'yes'}

                else:
                    current_start_index = additional_toc_pages[-1] + 1
            print('index not found')
            _stage_log("check_toc", "completed", toc_pages=len(toc_page_list), mode="toc_without_page_numbers")
            return {'toc_content': toc_json['toc_content'], 'toc_page_list': toc_page_list, 'page_index_given_in_toc': 'no'}






################### fix incorrect toc #########################################################
async def single_toc_item_index_fixer(section_title, content, model=None):
    toc_extractor_prompt = """
    You are given a section title and several pages of a document, your job is to find the physical index of the start page of the section in the partial document.

    The provided pages contains tags like <physical_index_X> and <physical_index_X> to indicate the physical location of the page X.

    Reply in a JSON format:
    {
        "thinking": <explain which page, started and closed by <physical_index_X>, contains the start of this section>,
        "physical_index": "<physical_index_X>" (keep the format)
    }
    Directly return the final JSON structure. Do not output anything else."""

    prompt = toc_extractor_prompt + '\nSection Title:\n' + str(section_title) + '\nDocument pages:\n' + content
    response = await llm_acompletion(model=model, prompt=prompt, debug_label="single_toc_item_index_fixer")
    json_content = extract_json(response, debug_label="single_toc_item_index_fixer")    
    return convert_physical_index_to_int(json_content['physical_index'])



async def fix_incorrect_toc(toc_with_page_number, page_list, incorrect_results, start_index=1, model=None, logger=None):
    print(f'start fix_incorrect_toc with {len(incorrect_results)} incorrect results')
    incorrect_indices = {result['list_index'] for result in incorrect_results}
    
    end_index = len(page_list) + start_index - 1
    
    incorrect_results_and_range_logs = []
    # Helper function to process and check a single incorrect item
    async def process_and_check_item(incorrect_item):
        list_index = incorrect_item['list_index']
        
        # Check if list_index is valid
        if list_index < 0 or list_index >= len(toc_with_page_number):
            # Return an invalid result for out-of-bounds indices
            return {
                'list_index': list_index,
                'title': incorrect_item['title'],
                'physical_index': incorrect_item.get('physical_index'),
                'is_valid': False
            }
        
        # Find the previous correct item
        prev_correct = None
        for i in range(list_index-1, -1, -1):
            if i not in incorrect_indices and i >= 0 and i < len(toc_with_page_number):
                physical_index = toc_with_page_number[i].get('physical_index')
                if physical_index is not None:
                    prev_correct = physical_index
                    break
        # If no previous correct item found, use start_index
        if prev_correct is None:
            prev_correct = start_index - 1
        
        # Find the next correct item
        next_correct = None
        for i in range(list_index+1, len(toc_with_page_number)):
            if i not in incorrect_indices and i >= 0 and i < len(toc_with_page_number):
                physical_index = toc_with_page_number[i].get('physical_index')
                if physical_index is not None:
                    next_correct = physical_index
                    break
        # If no next correct item found, use end_index
        if next_correct is None:
            next_correct = end_index
        
        incorrect_results_and_range_logs.append({
            'list_index': list_index,
            'title': incorrect_item['title'],
            'prev_correct': prev_correct,
            'next_correct': next_correct
        })

        page_contents=[]
        for page_index in range(prev_correct, next_correct+1):
            # Add bounds checking to prevent IndexError
            page_list_idx = page_index - start_index
            if page_list_idx >= 0 and page_list_idx < len(page_list):
                page_text = f"<physical_index_{page_index}>\n{page_list[page_list_idx][0]}\n<physical_index_{page_index}>\n\n"
                page_contents.append(page_text)
            else:
                continue
        content_range = ''.join(page_contents)
        
        physical_index_int = await single_toc_item_index_fixer(incorrect_item['title'], content_range, model)
        
        # Check if the result is correct
        check_item = incorrect_item.copy()
        check_item['physical_index'] = physical_index_int
        check_result = await check_title_appearance(check_item, page_list, start_index, model)

        return {
            'list_index': list_index,
            'title': incorrect_item['title'],
            'physical_index': physical_index_int,
            'is_valid': check_result['answer'] == 'yes'
        }

    # Process incorrect items concurrently
    tasks = [
        process_and_check_item(item)
        for item in incorrect_results
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    flush_litellm_logging_worker_sync(timeout_seconds=2.0)
    for item, result in zip(incorrect_results, results):
        if isinstance(result, Exception):
            print(f"Processing item {item} generated an exception: {result}")
            continue
    results = [result for result in results if not isinstance(result, Exception)]

    # Update the toc_with_page_number with the fixed indices and check for any invalid results
    invalid_results = []
    for result in results:
        if result['is_valid']:
            # Add bounds checking to prevent IndexError
            list_idx = result['list_index']
            if 0 <= list_idx < len(toc_with_page_number):
                toc_with_page_number[list_idx]['physical_index'] = result['physical_index']
            else:
                # Index is out of bounds, treat as invalid
                invalid_results.append({
                    'list_index': result['list_index'],
                    'title': result['title'],
                    'physical_index': result['physical_index'],
                })
        else:
            invalid_results.append({
                'list_index': result['list_index'],
                'title': result['title'],
                'physical_index': result['physical_index'],
            })

    logger.info(f'incorrect_results_and_range_logs: {incorrect_results_and_range_logs}')
    logger.info(f'invalid_results: {invalid_results}')

    return toc_with_page_number, invalid_results



async def fix_incorrect_toc_with_retries(toc_with_page_number, page_list, incorrect_results, start_index=1, max_attempts=3, model=None, logger=None):
    print('start fix_incorrect_toc')
    fix_attempt = 0
    current_toc = toc_with_page_number
    current_incorrect = incorrect_results

    while current_incorrect:
        print(f"Fixing {len(current_incorrect)} incorrect results")
        
        current_toc, current_incorrect = await fix_incorrect_toc(current_toc, page_list, current_incorrect, start_index, model, logger)
                
        fix_attempt += 1
        if fix_attempt >= max_attempts:
            logger.info("Maximum fix attempts reached")
            break
    
    return current_toc, current_incorrect




################### verify toc #########################################################
async def verify_toc(page_list, list_result, start_index=1, N=None, model=None):
    print('start verify_toc')
    start_time = time.perf_counter()
    # Find the last non-None physical_index
    last_physical_index = None
    for item in reversed(list_result):
        if item.get('physical_index') is not None:
            last_physical_index = item['physical_index']
            break
    
    # Early return if we don't have valid physical indices
    if last_physical_index is None or last_physical_index < len(page_list)/2:
        return 0, []
    
    # Determine which items to check
    if N is None:
        print('check all items')
        sample_indices = range(0, len(list_result))
    else:
        N = min(N, len(list_result))
        print(f'check {N} items')
        sample_indices = random.sample(range(0, len(list_result)), N)

    # Prepare items with their list indices
    indexed_sample_list = []
    for idx in sample_indices:
        item = list_result[idx]
        # Skip items with None physical_index (these were invalidated by validate_and_truncate_physical_indices)
        if item.get('physical_index') is not None:
            item_with_index = item.copy()
            item_with_index['list_index'] = idx  # Add the original index in list_result
            indexed_sample_list.append(item_with_index)

    # Run checks concurrently
    tasks = [
        check_title_appearance(item, page_list, start_index, model)
        for item in indexed_sample_list
    ]
    results = await asyncio.gather(*tasks)
    flush_litellm_logging_worker_sync(timeout_seconds=2.0)

    # Process results
    correct_count = 0
    incorrect_results = []
    for result in results:
        if result['answer'] == 'yes':
            correct_count += 1
        else:
            incorrect_results.append(result)
    
    # Calculate accuracy
    checked_count = len(results)
    accuracy = correct_count / checked_count if checked_count > 0 else 0
    print(f"accuracy: {accuracy*100:.2f}%")
    _stage_log(
        "verify_toc",
        "completed",
        checked_count=checked_count,
        incorrect_count=len(incorrect_results),
        accuracy=round(accuracy, 4),
        duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
    )
    return accuracy, incorrect_results





################### main process #########################################################
async def meta_processor(page_list, mode=None, toc_content=None, toc_page_list=None, start_index=1, opt=None, logger=None):
    print(mode)
    print(f'start_index: {start_index}')
    
    if mode == 'process_toc_with_page_numbers':
        toc_with_page_number = process_toc_with_page_numbers(toc_content, toc_page_list, page_list, toc_check_page_num=opt.toc_check_page_num, model=opt.model, logger=logger)
    elif mode == 'process_toc_no_page_numbers':
        toc_with_page_number = process_toc_no_page_numbers(toc_content, toc_page_list, page_list, model=opt.model, logger=logger)
    else:
        toc_with_page_number = process_no_toc(page_list, start_index=start_index, model=opt.model, logger=logger)
            
    toc_with_page_number = [item for item in toc_with_page_number if item.get('physical_index') is not None] 
    
    toc_with_page_number = validate_and_truncate_physical_indices(
        toc_with_page_number, 
        len(page_list), 
        start_index=start_index, 
        logger=logger
    )
    
    accuracy, incorrect_results = await verify_toc(page_list, toc_with_page_number, start_index=start_index, model=opt.model)
        
    logger.info({
        'mode': 'process_toc_with_page_numbers',
        'accuracy': accuracy,
        'incorrect_results': incorrect_results
    })
    if accuracy == 1.0 and len(incorrect_results) == 0:
        return toc_with_page_number
    if accuracy > 0.6 and len(incorrect_results) > 0:
        toc_with_page_number, incorrect_results = await fix_incorrect_toc_with_retries(toc_with_page_number, page_list, incorrect_results,start_index=start_index, max_attempts=3, model=opt.model, logger=logger)
        return toc_with_page_number
    else:
        if mode == 'process_toc_with_page_numbers':
            return await meta_processor(page_list, mode='process_toc_no_page_numbers', toc_content=toc_content, toc_page_list=toc_page_list, start_index=start_index, opt=opt, logger=logger)
        elif mode == 'process_toc_no_page_numbers':
            return await meta_processor(page_list, mode='process_no_toc', start_index=start_index, opt=opt, logger=logger)
        else:
            raise Exception('Processing failed')
        
 
async def process_large_node_recursively(node, page_list, opt=None, logger=None):
    return await process_large_node_recursively_with_depth(node, page_list, opt=opt, logger=logger, current_depth=1)


def _node_should_attempt_recursive_split(node, node_page_list, opt, current_depth):
    if str(getattr(opt, "recursive_split_enabled", "yes")).strip().lower() != "yes":
        return False
    if current_depth >= getattr(opt, "recursive_split_max_depth", 3):
        return False
    if node.get("nodes"):
        return False
    page_span = node["end_index"] - node["start_index"] + 1
    token_num = sum(page[1] for page in node_page_list)
    return (
        page_span >= getattr(opt, "recursive_split_min_pages", 4)
        or token_num >= getattr(opt, "recursive_split_min_tokens", 2000)
    )


def _build_children_from_heading_candidates(parent_node, candidates):
    if not candidates:
        return []

    children = []
    for index, candidate in enumerate(candidates):
        start_index = candidate["physical_index"]
        if index < len(candidates) - 1:
            next_start = candidates[index + 1]["physical_index"]
            end_index = next_start - 1 if next_start > start_index else next_start
        else:
            end_index = parent_node["end_index"]

        if end_index < start_index:
            continue

        children.append(
            {
                "title": candidate["title"],
                "start_index": start_index,
                "end_index": end_index,
            }
        )

    if len(children) >= 2:
        start_pages = [child["start_index"] for child in children]
        if start_pages == sorted(start_pages) and len(start_pages) == len(set(start_pages)):
            return children

    if len(children) == 1:
        child = children[0]
        if child["title"].strip().lower() != parent_node["title"].strip().lower():
            return children

    return []


async def process_large_node_recursively_with_depth(node, page_list, opt=None, logger=None, current_depth=1):
    node_page_list = page_list[node['start_index']-1:node['end_index']]
    token_num = sum([page[1] for page in node_page_list])
    _stage_log(
        "recursive_split",
        "inspect_node",
        logger=logger,
        title=node.get("title"),
        depth=current_depth,
        start_index=node.get("start_index"),
        end_index=node.get("end_index"),
        token_num=token_num,
    )

    if _node_should_attempt_recursive_split(node, node_page_list, opt, current_depth):
        heading_candidates = extract_heading_candidates_from_page_list(
            node_page_list,
            node["start_index"],
            parent_title=node.get("title"),
            heading_patterns=getattr(opt, "recursive_split_heading_patterns", None),
        )
        heuristic_children = _build_children_from_heading_candidates(node, heading_candidates)
        if heuristic_children:
            node["nodes"] = heuristic_children
            _stage_log(
                "recursive_split",
                "heuristic_children_created",
                logger=logger,
                title=node.get("title"),
                depth=current_depth,
                child_count=len(heuristic_children),
            )
            if logger:
                logger.info(
                    {
                        "mode": "heuristic_recursive_split",
                        "title": node.get("title"),
                        "start_index": node.get("start_index"),
                        "end_index": node.get("end_index"),
                        "children": [{"title": child["title"], "start_index": child["start_index"], "end_index": child["end_index"]} for child in heuristic_children],
                    }
                )
        else:
            _stage_log(
                "recursive_split",
                "heuristic_split_skipped",
                logger=logger,
                title=node.get("title"),
                depth=current_depth,
                candidate_count=len(heading_candidates),
            )

    if not node.get("nodes") and node['end_index'] - node['start_index'] > opt.max_page_num_each_node and token_num >= opt.max_token_num_each_node:
        print('large node:', node['title'], 'start_index:', node['start_index'], 'end_index:', node['end_index'], 'token_num:', token_num)
        _stage_log(
            "recursive_split",
            "llm_fallback_started",
            logger=logger,
            title=node.get("title"),
            depth=current_depth,
        )

        node_toc_tree = await meta_processor(node_page_list, mode='process_no_toc', start_index=node['start_index'], opt=opt, logger=logger)
        node_toc_tree = await check_title_appearance_in_start_concurrent(node_toc_tree, page_list, model=opt.model, logger=logger)
        
        # Filter out items with None physical_index before post_processing
        valid_node_toc_items = [item for item in node_toc_tree if item.get('physical_index') is not None]
        
        if valid_node_toc_items and node['title'].strip() == valid_node_toc_items[0]['title'].strip():
            node['nodes'] = post_processing(valid_node_toc_items[1:], node['end_index'])
            node['end_index'] = valid_node_toc_items[1]['start_index'] if len(valid_node_toc_items) > 1 else node['end_index']
        else:
            node['nodes'] = post_processing(valid_node_toc_items, node['end_index'])
            node['end_index'] = valid_node_toc_items[0]['start_index'] if valid_node_toc_items else node['end_index']
        _stage_log(
            "recursive_split",
            "llm_fallback_completed",
            logger=logger,
            title=node.get("title"),
            depth=current_depth,
            child_count=len(node.get("nodes", []) or []),
        )
    
    if 'nodes' in node and node['nodes']:
        tasks = [
            process_large_node_recursively_with_depth(child_node, page_list, opt, logger=logger, current_depth=current_depth + 1)
            for child_node in node['nodes']
        ]
        await asyncio.gather(*tasks)
    
    return node

async def tree_parser(page_list, opt, doc=None, logger=None):
    check_toc_result = check_toc(page_list, opt)
    logger.info(check_toc_result)

    if check_toc_result.get("toc_content") and check_toc_result["toc_content"].strip() and check_toc_result["page_index_given_in_toc"] == "yes":
        toc_with_page_number = await meta_processor(
            page_list, 
            mode='process_toc_with_page_numbers', 
            start_index=1, 
            toc_content=check_toc_result['toc_content'], 
            toc_page_list=check_toc_result['toc_page_list'], 
            opt=opt,
            logger=logger)
    else:
        toc_with_page_number = await meta_processor(
            page_list, 
            mode='process_no_toc', 
            start_index=1, 
            opt=opt,
            logger=logger)

    toc_with_page_number = add_preface_if_needed(toc_with_page_number)
    toc_with_page_number = await check_title_appearance_in_start_concurrent(toc_with_page_number, page_list, model=opt.model, logger=logger)
    
    # Filter out items with None physical_index before post_processings
    valid_toc_items = [item for item in toc_with_page_number if item.get('physical_index') is not None]
    
    toc_tree = post_processing(valid_toc_items, len(page_list))
    tasks = [
        process_large_node_recursively_with_depth(node, page_list, opt, logger=logger, current_depth=1)
        for node in toc_tree
    ]
    await asyncio.gather(*tasks)
    
    return toc_tree


def build_pdf_tree_from_opt(doc, opt=None):
    logger = JsonLogger(doc)
    
    is_valid_pdf = (
        (isinstance(doc, str) and os.path.isfile(doc) and doc.lower().endswith(".pdf")) or 
        isinstance(doc, BytesIO)
    )
    if not is_valid_pdf:
        raise ValueError("Unsupported input type. Expected a PDF file path or BytesIO object.")

    print('Parsing PDF...')
    page_list = get_page_tokens(doc, model=opt.model)
    _stage_log("llm_limits", "configured", logger=logger, **get_llm_runtime_limits())

    logger.info({'total_page_number': len(page_list)})
    logger.info({'total_token': sum([page[1] for page in page_list])})

    async def build_tree():
        try:
            structure = await tree_parser(page_list, opt, doc=doc, logger=logger)
            if opt.if_add_node_id == 'yes':
                write_node_id(structure)    
            if opt.if_add_node_text == 'yes':
                add_node_text(structure, page_list)
            if opt.if_add_node_summary == 'yes':
                if opt.if_add_node_text == 'no':
                    add_node_text(structure, page_list)
                await generate_summaries_for_structure(structure, model=opt.model)
                if opt.if_add_node_text == 'no':
                    remove_structure_text(structure)
                if opt.if_add_doc_description == 'yes':
                    # Create a clean structure without unnecessary fields for description generation
                    clean_structure = create_clean_structure_for_description(structure)
                    doc_description = generate_doc_description(clean_structure, model=opt.model)
                    return {
                        'doc_name': get_pdf_name(doc),
                        'doc_description': doc_description,
                        'structure': structure,
                    }
            return {
                'doc_name': get_pdf_name(doc),
                'structure': structure,
            }
        finally:
            await flush_litellm_logging_worker(stop_worker=False)

    return asyncio.run(build_tree())


def build_pdf_tree(doc, model=None, toc_check_page_num=None, max_page_num_each_node=None, max_token_num_each_node=None,
                   if_add_node_id=None, if_add_node_summary=None, if_add_doc_description=None, if_add_node_text=None):
    
    user_opt = {
        arg: value for arg, value in locals().items()
        if arg != "doc" and value is not None
    }
    opt = ConfigLoader().load(user_opt)
    return build_pdf_tree_from_opt(doc, opt)


def validate_and_truncate_physical_indices(toc_with_page_number, page_list_length, start_index=1, logger=None):
    """
    Validates and truncates physical indices that exceed the actual document length.
    This prevents errors when TOC references pages that don't exist in the document (e.g. the file is broken or incomplete).
    """
    if not toc_with_page_number:
        return toc_with_page_number
    
    max_allowed_page = page_list_length + start_index - 1
    truncated_items = []
    
    for i, item in enumerate(toc_with_page_number):
        if item.get('physical_index') is not None:
            original_index = item['physical_index']
            if original_index > max_allowed_page:
                item['physical_index'] = None
                truncated_items.append({
                    'title': item.get('title', 'Unknown'),
                    'original_index': original_index
                })
                if logger:
                    logger.info(f"Removed physical_index for '{item.get('title', 'Unknown')}' (was {original_index}, too far beyond document)")
    
    if truncated_items and logger:
        logger.info(f"Total removed items: {len(truncated_items)}")
        
    print(f"Document validation: {page_list_length} pages, max allowed index: {max_allowed_page}")
    if truncated_items:
        print(f"Truncated {len(truncated_items)} TOC items that exceeded document length")
     
    return toc_with_page_number
