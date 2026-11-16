# Scope: Milestone 1 - Asset Permissions & Filesystem Integrity

## Architecture
- Target directory: `c:\Users\Chosen033\Documents\Guardian-Runner\assets\graphics\GandalfHardcore Hell Asset Pack 32x32`
- Root issue: Restrictive NTFS DACLs / unmapped SID ownership (`...`) preventing read, write, and directory traversal access across 51 files and 36 directories.
- Resolution: Grant open read/write/execution inheritance ACLs recursively (e.g. via `icacls`, `takeown`, or Python `os.chmod` scripts) within default sandbox permissions without requiring sandbox elevation.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Filesystem ACL Restoration | Restore open read/execute/write permissions on all 51 files and 36 directories in `GandalfHardcore Hell Asset Pack 32x32` | M1 | Survey |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Asset Permissions & Filesystem Integrity | Fix ACLs on `assets/graphics/GandalfHardcore Hell Asset Pack 32x32` | none | IN_PROGRESS |

## Interface Contracts
### Asset Directory File System Access
- **Input**: Any file or directory path within `c:\Users\Chosen033\Documents\Guardian-Runner\assets\graphics\GandalfHardcore Hell Asset Pack 32x32`.
- **Output**: Openable for read, write, and directory listing without `PermissionError: [Errno 13] Permission denied` or `PermissionError: [WinError 5] Access is denied`.
- **Validation**:
  - `[System.IO.File]::OpenRead($file.FullName).Close()` succeeds on 100% of files.
  - Python `open(path, 'rb').read(1)` succeeds on 100% of files.
  - `os.listdir(dir_path)` succeeds on 100% of directories.

## Code Layout
- State folder: `c:\Users\Chosen033\Documents\Guardian-Runner\.agents\teamwork\sub_orch_m1`
- Target path: `c:\Users\Chosen033\Documents\Guardian-Runner\assets\graphics\GandalfHardcore Hell Asset Pack 32x32`
