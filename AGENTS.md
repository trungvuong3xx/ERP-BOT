# AGENTS.md

Project-level behavioral and tooling guidelines.

## Skills Index

| Skill | Topic |
| --- | --- |
| `brainstorming` | Design & planning: explore intent, constraints, propose approaches, get approval |
| `core-asset-usage` | Runtime config: Asset access patterns, PO/NonPO placement, UtilsHelper static usage |
| `core-browser-automation` | Playwright: BrowserSession, BrowserPage, navigation, interaction, waits, iframe |
| `core-extensions` | Helpers: StringExtensions, NumberExtensions, EnumExtensions, XmlExtensions |
| `logging` | Logging: LogEnter/LogLeave, Log/Warning/Error, [] formatting, | separator |
| `codebase-memory` | MCP graph: search_graph, trace_path, detect_changes, index_repository |
| `erp-igp-automation` | Quy trình tự động hóa nhập liệu chứng từ WorkFlow ERP iGP từ Google Sheets (Chỉ & Nhựa) |
| `karpathy-guidelines` | Behavioral guidelines derived from Andrej Karpathy to reduce common LLM coding mistakes |

## Quick Reference

**Before any task:**

1. Invoke `brainstorming` skill — no exceptions

**Before editing code:**

1. Invoke `codebase-memory` skill → `search_graph` + `trace_path(direction="inbound")`
2. Read `logging` skill for any function you write or modify

**After code changes:**

1. `detect_changes()` → verify affected scope
2. `index_repository(mode="full")` → sync knowledge graph
3. Luôn rà soát lại toàn bộ logic ở các phần khác có liên quan đến đoạn code vừa được thêm/sửa/xóa để kịp thời đồng bộ, tránh phát sinh lỗi hiển thị hoặc sai lệch dữ liệu.