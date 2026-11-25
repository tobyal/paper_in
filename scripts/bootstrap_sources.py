"""Reconstruct the pinned upstream sources and recorded source adaptations."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def git(repo, *args, check=True):
    return subprocess.run(
        ['git', '-C', str(repo), *args], check=check,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true',
                        help='Check existing sources without downloading or applying patches.')
    args = parser.parse_args()
    sources = json.loads((ROOT / 'UPSTREAM.lock.json').read_text(encoding='utf-8'))['sources']
    for source in sources:
        repo = ROOT / source['path']
        if not (repo / '.git').exists():
            if args.verify_only:
                raise SystemExit(f'Missing submodule: {source["path"]}')
            git(ROOT, 'submodule', 'update', '--init', '--recursive', '--', source['path'])
        commit = git(repo, 'rev-parse', 'HEAD').stdout.strip()
        if commit != source['commit']:
            raise SystemExit(f'{source["path"]}: expected {source["commit"]}, found {commit}; no reset performed.')
        patch = ROOT / source['patch']
        digest = hashlib.sha256(patch.read_bytes()).hexdigest()
        if digest != source['patch_sha256']:
            raise SystemExit(f'Patch checksum mismatch: {patch}')
        if git(repo, 'apply', '--reverse', '--check', str(patch), check=False).returncode == 0:
            print(f'{source["path"]}: pinned commit and patch verified')
            continue
        if args.verify_only:
            raise SystemExit(f'{source["path"]}: recorded patch is not fully applied')
        git(repo, 'apply', '--check', str(patch))
        git(repo, 'apply', str(patch))
        print(f'{source["path"]}: recorded source patch applied')
    print('Source preparation complete. Build extensions and prepare data/models separately.')


if __name__ == '__main__':
    main()
