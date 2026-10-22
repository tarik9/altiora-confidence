"""Start the Altiora Confidence desktop app.

Hidden check used by the build script:  "Altiora Confidence.exe" --selftest file.pdf result_folder
"""
import sys


def selftest(pdf, out_dir):
    from pathlib import Path
    from app import engine

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    lines = []
    try:
        a = engine.analyze(pdf)
        r = engine.apply(a, out / "selftest_anonymise.pdf")
        ok = a.ai_available and r.hidden_count > 0 and not r.leaks
        lines += [f"ai_model={'ok' if a.ai_available else 'MISSING'}",
                  f"ocr_languages={engine.ocr_languages() or 'MISSING'}",
                  f"hidden={r.hidden_count}", f"leaks={len(r.leaks)}", "RESULT=" + ("OK" if ok else "PROBLEM")]
    except Exception as e:  # pragma: no cover
        lines += [f"error={e!r}", "RESULT=PROBLEM"]
    (out / "selftest.txt").write_text("\n".join(lines), encoding="utf-8")
    return 0 if lines[-1] == "RESULT=OK" else 1


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--selftest":
        sys.exit(selftest(sys.argv[2], sys.argv[3]))
    from app.gui import main

    main()
