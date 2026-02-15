# Build script for GroceryGuard Chatbot
# This script prepares a production-ready build of the chatbot.

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BUILD_DIR = PROJECT_ROOT / 'build'


def run_step(cmd: list[str], label: str, cwd: Path | None = None) -> None:
    print(f'{label}...')
    subprocess.run(cmd, check=True, cwd=str(cwd) if cwd else None)


def main() -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Install dependencies
    run_step([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 'Installing dependencies')

    # 2. Run tests
    run_step([sys.executable, '-m', 'pytest', 'tests'], 'Running tests', cwd=PROJECT_ROOT / 'src')

    # 3. Prepare results folders
    print('Ensuring results folders exist...')
    (PROJECT_ROOT / 'results' / 'transcripts').mkdir(parents=True, exist_ok=True)

    # 4. Copy static web files (if any)
    web_dir = PROJECT_ROOT / 'web'
    if web_dir.exists():
        build_web_dir = BUILD_DIR / 'web'
        build_web_dir.mkdir(parents=True, exist_ok=True)
        for file in web_dir.iterdir():
            if file.is_file():
                shutil.copy(file, build_web_dir)
        print('Copied web files to build/web/')

    # 5. Copy data files
    print('Copying data files...')
    data_dir = PROJECT_ROOT / 'data'
    build_data_dir = BUILD_DIR / 'data'
    build_data_dir.mkdir(parents=True, exist_ok=True)
    for file in data_dir.iterdir():
        if file.is_file():
            shutil.copy(file, build_data_dir)

    # 6. Copy source code
    print('Copying source code...')
    src_dir = PROJECT_ROOT / 'src'
    build_src_dir = BUILD_DIR / 'src'
    if build_src_dir.exists():
        shutil.rmtree(build_src_dir)
    shutil.copytree(src_dir, build_src_dir)

    # 7. Copy evaluation artifacts
    print('Copying evaluation artifacts...')
    results_dir = PROJECT_ROOT / 'results'
    build_results_dir = BUILD_DIR / 'results'
    if build_results_dir.exists():
        shutil.rmtree(build_results_dir)
    build_results_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = results_dir / 'metrics.json'
    transcripts_dir = results_dir / 'transcripts'
    if metrics_path.exists():
        shutil.copy(metrics_path, build_results_dir / 'metrics.json')
    if transcripts_dir.exists():
        shutil.copytree(transcripts_dir, build_results_dir / 'transcripts')

    # 8. Copy requirements.txt and README
    shutil.copy(PROJECT_ROOT / 'requirements.txt', BUILD_DIR / 'requirements.txt')
    if (PROJECT_ROOT / 'README.md').exists():
        shutil.copy(PROJECT_ROOT / 'README.md', BUILD_DIR / 'README.md')
    for doc_name in ['ABLATION_STUDY.md', 'LONG_TERM_MEMORY.md']:
        doc_path = PROJECT_ROOT / doc_name
        if doc_path.exists():
            shutil.copy(doc_path, BUILD_DIR / doc_name)

    print('Build complete! The build is in the build/ directory.')


if __name__ == '__main__':
    main()
