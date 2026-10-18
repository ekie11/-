"""UNO-скрипт: запускается интерпретатором, у которого есть `import uno` (см. lo_pages).

Аргументы: soffice, каталог профиля, копия DOCX, выходной PDF.
Печатает в stdout JSON {закладка _Toc…: страница}. Оригинал DOCX не трогает.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time


def main(soffice: str, profile: str, src: str, out_pdf: str) -> None:
    import uno
    from com.sun.star.beans import PropertyValue

    def pv(name, value):
        p = PropertyValue()
        p.Name, p.Value = name, value
        return p

    pipe = f"gostdoc{os.getpid()}"
    proc = subprocess.Popen(
        [
            soffice,
            "--headless",
            "--invisible",
            "--norestore",
            f"-env:UserInstallation=file://{profile}",
            f"--accept=pipe,name={pipe};urp;",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ctx = uno.getComponentContext()
        resolver = ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", ctx
        )
        remote = None
        for _ in range(240):
            try:
                remote = resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
                break
            except Exception:  # noqa: BLE001 - UNO бросает разные исключения, пока soffice стартует
                if proc.poll() is not None:
                    raise SystemExit("soffice завершился")
                time.sleep(0.25)
        if remote is None:
            raise SystemExit("нет соединения с soffice")
        desktop = remote.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", remote
        )
        doc = desktop.loadComponentFromURL(
            "file://" + os.path.abspath(src), "_blank", 0, (pv("Hidden", True),)
        )
        if doc is None:
            raise SystemExit("документ не открылся")
        indexes = doc.getDocumentIndexes()
        for _ in range(2):
            for i in range(indexes.getCount()):
                indexes.getByIndex(i).update()
            doc.refresh()
        view = doc.getCurrentController().getViewCursor()
        pages: dict[str, int] = {}
        bookmarks = doc.getBookmarks()
        for name in bookmarks.getElementNames():
            if not name.startswith("_Toc"):
                continue
            view.gotoRange(bookmarks.getByName(name).getAnchor().getStart(), False)
            pages[name] = int(view.getPage())
        doc.storeToURL(
            "file://" + os.path.abspath(out_pdf), (pv("FilterName", "writer_pdf_Export"),)
        )
        doc.close(True)
        sys.stdout.write(json.dumps(pages))
        sys.stdout.flush()
    finally:
        proc.kill()


if __name__ == "__main__":
    main(*sys.argv[1:5])
