"""Adobe dng_validate may return zero despite diagnostics. Check its text too."""
import argparse
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('validator')
    parser.add_argument('dng')
    args = parser.parse_args()
    result = subprocess.run([args.validator, '-v', args.dng], capture_output=True, text=True, timeout=180)
    text = result.stdout + result.stderr
    print(text)
    if result.returncode or '*** Error' in text or '*** Warning' in text or 'Validation complete' not in text:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
