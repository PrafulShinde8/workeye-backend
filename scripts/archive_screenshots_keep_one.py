import os
import shutil

ROOT = os.path.dirname(os.path.dirname(__file__))
SCREENSHOT_DIR = os.path.join(ROOT, 'screenshots')
ARCHIVE_DIR = os.path.join(ROOT, 'screenshots_archive')
KEEP_PATH = os.path.join(SCREENSHOT_DIR, '12', '40', 'screenshot_235_20260202_104606.webp')

os.makedirs(ARCHIVE_DIR, exist_ok=True)

# Move everything to archive
if os.path.isdir(SCREENSHOT_DIR):
    for name in os.listdir(SCREENSHOT_DIR):
        src = os.path.join(SCREENSHOT_DIR, name)
        dest = os.path.join(ARCHIVE_DIR, name)
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.move(src, dest)
    print(f'Moved {SCREENSHOT_DIR} -> {ARCHIVE_DIR}')
else:
    print('No screenshots dir to archive')

# Restore the one file if it exists in archive
keep_found = False
for root, dirs, files in os.walk(ARCHIVE_DIR):
    for f in files:
        path = os.path.join(root, f)
        if os.path.normcase(path) == os.path.normcase(KEEP_PATH.replace(SCREENSHOT_DIR, ARCHIVE_DIR)):
            # compute target path
            tgt_dir = os.path.dirname(KEEP_PATH)
            os.makedirs(tgt_dir, exist_ok=True)
            shutil.copy2(path, KEEP_PATH)
            keep_found = True
            print('Restored keep file to', KEEP_PATH)

if not keep_found:
    print('Keep file not found in archive; checking archive tree for similar file...')
    # Try to find by filename only
    for root, dirs, files in os.walk(ARCHIVE_DIR):
        for f in files:
            if f == 'screenshot_235_20260202_104606.webp':
                src = os.path.join(root, f)
                tgt_dir = os.path.dirname(KEEP_PATH)
                os.makedirs(tgt_dir, exist_ok=True)
                shutil.copy2(src, KEEP_PATH)
                keep_found = True
                print('Restored keep file to', KEEP_PATH)

if not keep_found:
    print('Keep file not found; nothing restored')
else:
    print('Archive complete.')