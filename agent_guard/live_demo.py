"""One model proposal followed by simulated guarded execution."""

import argparse
import sys

from .agent import execute_model_response
from .audit import audit_log
from .auth_tokens import AuthenticationError
from .model_client import ModelClient, ModelRequestError
from .oauth_callback import CallbackError
from .sign_in import sign_in
from .simulate import display_audit_log


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instruction", help='One instruction, e.g. "Read notes.txt"')
    parser.add_argument("--model", help="Use this slug from the signed-in account's catalog")
    args = parser.parse_args(argv)
    audit_log.clear()
    try:
        print("File operations are simulated. This command sends your instruction to a model.")
        print("Continue with ChatGPT in the browser.")
        client = ModelClient(sign_in())
        choices = client.list_models()
        selected = choices[0] if args.model is None else next(
            (choice for choice in choices if choice.slug == args.model), None,
        )
        if selected is None:
            print("Choose one of these account model slugs:")
            for choice in choices:
                print(f"  {choice.slug!r}: {choice.display_name!r}")
            return 2
        print(f"Model: {selected.display_name!r} ({selected.slug!r})")
        text = client.propose(args.instruction, selected.slug)
        print(f"Completed model proposal: {text!r}")
        allowed, message = execute_model_response(text)
        print("EXECUTED" if allowed else "DENIED")
        print(f"  {message}")
        display_audit_log()
        return 0
    except KeyboardInterrupt:
        print("Demo cancelled.", file=sys.stderr)
        return 130
    except (AuthenticationError, CallbackError, TimeoutError, ModelRequestError) as error:
        print(f"Demo stopped: {error}", file=sys.stderr)
        return 1
    except Exception:
        print("Demo stopped unexpectedly; private error details were suppressed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
