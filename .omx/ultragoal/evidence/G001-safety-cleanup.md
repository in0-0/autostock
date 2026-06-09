# G001 Safety Cleanup Evidence

- Removed current dirty debug prints from local worktree:
  - `src/main.py`: `print(api_key)`
  - `src/reporting.py`: `print(candidate)`
- Verified with `rg -n 'print\(api_key\)|print\(candidate\)' src/main.py src/reporting.py`: no matches.
- Verified no forbidden current-stage order/sizing instruction language in the changed source files.
- Source files returned to HEAD-equivalent for those debug-print changes; future stories can safely run non-live tests/smokes without those leak paths.
