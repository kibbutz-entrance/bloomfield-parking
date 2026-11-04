"""Best-effort persistence after publication; never overwrite a newer branch."""
import os
from pathlib import Path
import subprocess
import time


def git(*args):
    return subprocess.run(['git', *args], check=True, capture_output=True, text=True, timeout=45).stdout.strip()


def persist(attempts=3, delay=time.sleep):
    base = git('rev-parse', 'HEAD')
    git('config', 'user.name', 'parking-bot')
    git('config', 'user.email', 'parking-bot@users.noreply.github.com')
    git('add', '--', 'games.json', 'data/source-cache.json')
    if not git('diff', '--cached', '--name-only'):
        return 'unchanged'
    git('commit', '-m', 'Refresh official event schedules [skip ci]')
    snapshot = git('rev-parse', 'HEAD')
    for attempt in range(attempts):
        try:
            # Fetch before every push, including after an ambiguous network failure.
            git('fetch', '--no-tags', 'origin', 'main')
            remote = git('rev-parse', 'FETCH_HEAD')
            try:
                git('merge-base', '--is-ancestor', snapshot, remote)
                return 'saved'
            except subprocess.CalledProcessError as error:
                if error.returncode != 1:
                    raise
            if remote != base:
                # A new revision owns the next refresh. Do not rebase stale data.
                return 'superseded'
            git('push', 'origin', 'HEAD:refs/heads/main')
            # Verify remotely; a successful response alone is not the final check.
            git('fetch', '--no-tags', 'origin', 'main')
            git('merge-base', '--is-ancestor', snapshot, 'FETCH_HEAD')
            return 'saved'
        except (subprocess.SubprocessError, OSError):
            if attempt + 1 < attempts:
                delay(2 ** (attempt + 1))
    raise RuntimeError('Snapshot persistence failed after bounded retries; website deployment is independent')


if __name__ == '__main__':
    try:
        outcome = persist()
    except Exception:
        print('::error::Could not save the source snapshot after three attempts. Website was already deployed.')
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as output:
                output.write('Source backup FAILED after retries. Website deployment already succeeded. The source-snapshot artifact is retained for recovery.\n')
        raise
    message = {'saved': 'Source snapshot saved and verified.', 'unchanged': 'Source snapshot unchanged.',
               'superseded': 'Source snapshot not saved: main advanced; the newer revision owns the next refresh.'}[outcome]
    print(message)
    if outcome == 'superseded':
        print('::warning::' + message)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as output:
            output.write(message + '\n')
