import py_compile
import glob

def main():
    files = glob.glob('**/*.py', recursive=True) + glob.glob('*.py')
    errs = []
    for f in sorted(set(files)):
        try:
            py_compile.compile(f, doraise=True)
        except Exception as e:
            errs.append((f, str(e)))
    if errs:
        print('SYNTAX ERRORS:')
        for a, b in errs:
            print(f"{a}: {b}")
        return 1
    else:
        print('No syntax errors')
        return 0

if __name__ == '__main__':
    raise SystemExit(main())
