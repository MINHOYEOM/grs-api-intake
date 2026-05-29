#!/usr/bin/env python3
"""ogLmPp(입법예고 목록 조회) 응답 스키마 1회 진단용 — 일회성, 표준 라이브러리만 사용.

사용법 (repo 폴더에서):
    py -3 probe_oglmpp.py grmintake
    # OC 생략 시 OC=test 샘플로 시도
    py -3 probe_oglmpp.py

목적: 실제 XML의 루트/반복 항목 엘리먼트와 자식 태그명을 덤프해
      collect_mfds._collect_legislative_datago() 의 정확한 parser 를 작성하기 위함.
출력 전체를 그대로 채팅에 붙여넣어 주세요. (민감정보 아님 — OC는 공개 식별자)
"""

from __future__ import annotations

import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "GRM-probe/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def retmsg_error(raw: bytes) -> str:
    """법제처 API는 HTTP 200 + <retMsg>401</retMsg>처럼 오류를 XML 본문에 담기도 한다."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return ""
    if root.tag != "result":
        return ""
    ret_msg = root.findtext("retMsg")
    if ret_msg and len(list(root)) == 1:
        return ret_msg.strip()
    return ""


def is_html_response(raw: bytes) -> bool:
    stripped = raw.lstrip()[:100].lower()
    return stripped.startswith(b"<!doctype html") or stripped.startswith(b"<html")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    oc = sys.argv[1] if len(sys.argv) > 1 else "test"
    base_variants = [
        # (설명, URL)
        ("www .xml type=XML", f"https://www.lawmaking.go.kr/rest/ogLmPp.xml?OC={oc}&type=XML"),
        ("www no-ext type=XML", f"https://www.lawmaking.go.kr/rest/ogLmPp?OC={oc}&type=XML"),
        ("opinion .xml type=XML", f"https://opinion.lawmaking.go.kr/rest/ogLmPp.xml?OC={oc}&type=XML"),
    ]

    raw = b""
    used_url = ""
    for label, url in base_variants:
        try:
            print(f"[TRY] {label}: {url}")
            raw = fetch(url)
            if raw and raw.strip():
                err = retmsg_error(raw)
                if err:
                    print(f"[API-ERR] retMsg={err} - 다음 variant 시도\n")
                    continue
                if is_html_response(raw):
                    print(f"[HTML] XML이 아니라 HTML 응답({len(raw)} bytes) - 다음 variant 시도\n")
                    continue
                used_url = url
                print(f"[OK] {len(raw)} bytes\n")
                break
            print("[EMPTY] 응답 비어있음\n")
        except Exception as e:  # noqa: BLE001
            print(f"[ERR] {e}\n")

    if not raw or not used_url:
        print("=== 유효한 XML variant 없음 — OC/권한/네트워크 확인 필요 ===")
        return 1

    # 원시 앞부분 (인코딩 가늠용)
    head = raw[:800]
    print("=== RAW HEAD (앞 800 bytes) ===")
    try:
        print(head.decode("utf-8"))
    except UnicodeDecodeError:
        print(head.decode("euc-kr", errors="replace"))
    print("=== /RAW HEAD ===\n")

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"[XML PARSE 실패] {e} - RAW HEAD 로 구조 판단 필요")
        return 1

    print(f"ROOT tag: {root.tag}")
    # 루트 직속 자식 태그 빈도 → 반복 항목 엘리먼트 추정
    child_tags = Counter(ch.tag for ch in root)
    print(f"ROOT children tag 빈도: {dict(child_tags)}\n")

    # 가장 많이 반복되는 자식을 '항목'으로 간주
    if not child_tags:
        print("자식 없음 — RAW HEAD 참고")
        return 0
    item_tag, item_count = child_tags.most_common(1)[0]
    print(f"추정 항목 엘리먼트: <{item_tag}>  (count={item_count})\n")

    items = root.findall(item_tag)
    # 항목의 자식 태그 집합
    field_tags: list[str] = []
    seen = set()
    for it in items:
        for ch in it:
            if ch.tag not in seen:
                seen.add(ch.tag)
                field_tags.append(ch.tag)
    print(f"항목 내부 필드 태그({len(field_tags)}개): {field_tags}\n")

    # 앞 2개 항목 전체 덤프
    for idx, it in enumerate(items[:2], 1):
        print(f"--- 항목 #{idx} ---")
        for ch in it:
            val = (ch.text or "").strip()
            if len(val) > 120:
                val = val[:120] + "…"
            print(f"  {ch.tag}: {val}")
        print()

    # 소관부처 후보값 수집 (cptOfiOrgCd 필터 확정용)
    print("=== 소관부처 관련 값 모음 (식약처 코드/명 확인용) ===")
    for it in items:
        for ch in it:
            if any(k in ch.tag for k in ("부처", "기관", "OfiOrg", "ofiOrg", "org")):
                print(f"  {ch.tag} = {(ch.text or '').strip()}")
        # 식약처 키워드 포함 항목 표시
    print(f"\nused_url: {used_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
