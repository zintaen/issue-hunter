from e2b_code_interpreter import Sandbox

def main():
    try:
        s = Sandbox.create()
        # This will exit with code 1 and output to stderr
        s.commands.run("echo 'hello stdout'; echo 'hello stderr' >&2; exit 1")
    except Exception as e:
        print("Exception caught:")
        print(repr(e))

main()
