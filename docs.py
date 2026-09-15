"""Pull the actual solicitation documents and turn them into Drive-ready text.

The point: Drive should hold the RFP itself, not only our assessment of it.

A binary PDF cannot go through the Drive connector -- content has to be emitted
as a tool-call argument, and a 1.9 MB solicitation is ~2.5 M base64 characters
(~624k tokens). The same document's extracted text is ~66 k characters (~16k
tokens). So we upload the TEXT, in full, plus the direct free download URL for
anyone who wants the original binary.

    python docs.py --sam <notice-id>              # list + fetch SAM attachments
    python docs.py --url <url> --name "RFP"       # any direct document URL
    python docs.py --sam <id> --out rfp-text.md   # write the Drive-ready file

ponytail: pypdf for PDFs, zipfile for .docx (a docx is a zip of XML -- no
dependency needed). Anything else is recorded as a link, not decoded.
"""
import argparse, io, json, os, re, sys, zipfile
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

SAM_RES = "https://sam.gov/api/prod/opps/v3/opportunities/%s/resources"
SAM_DL = "https://sam.gov/api/prod/opps/v3/opportunities/resources/files/%s/download"

MAX_BYTES = 25 * 1024 * 1024        # don't pull a 100 MB drawing set


def fetch(url, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(MAX_BYTES)


def sam_resources(notice_id):
    """Every attachment on a SAM notice: name, size, and a free download URL."""
    data = json.loads(fetch(SAM_RES % notice_id, timeout=45).decode("utf-8", "replace"))
    out = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("type") == "file" and o.get("resourceId"):
                out.append({"name": o.get("name", "unnamed"),
                            "size": o.get("size", 0),
                            "id": o["resourceId"],
                            "url": SAM_DL % o["resourceId"]})
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(data)
    # de-dup on resourceId, preserve order
    seen, uniq = set(), []
    for f in out:
        if f["id"] in seen:
            continue
        seen.add(f["id"])
        uniq.append(f)
    return uniq


def pdf_text(blob):
    try:
        import pypdf
    except ImportError:
        return "", "pypdf not installed"
    try:
        r = pypdf.PdfReader(io.BytesIO(blob))
        return "\n\n".join((p.extract_text() or "") for p in r.pages), ""
    except Exception as e:
        return "", "pdf parse failed: %s" % e


def docx_text(blob):
    """A .docx is a zip of XML. Pull the paragraph text without a dependency."""
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    except Exception as e:
        return "", "docx read failed: %s" % e
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    return re.sub(r"\n{3,}", "\n\n", text).strip(), ""


def extract(name, blob):
    low = name.lower()
    if low.endswith(".pdf"):
        return pdf_text(blob)
    if low.endswith(".docx"):
        return docx_text(blob)
    if low.endswith((".txt", ".md", ".csv")):
        return blob.decode("utf-8", "replace"), ""
    return "", "no text extractor for this type"


def render(title, source_url, files):
    """Drive-ready markdown: every document's full text, plus its original URL."""
    L = ["# %s" % title, "",
         "Solicitation documents, extracted to text so they are searchable in Drive.",
         "The original binaries stay at the issuer -- each section links its own.", "",
         "**Source:** %s" % source_url, ""]
    ok = [f for f in files if f.get("text")]
    L += ["**%d of %d documents extracted.**" % (len(ok), len(files)), "",
          "| Document | Size | Extracted |", "|---|---|---|"]
    for f in files:
        L.append("| %s | %s | %s |" % (
            f["name"], "%.1f MB" % (f["size"] / 1048576.0) if f["size"] else "?",
            "%d chars" % len(f["text"]) if f.get("text") else "no - %s" % f.get("error", "")))
    L.append("")
    for f in files:
        L += ["", "---", "", "## %s" % f["name"], "", "**Original:** %s" % f["url"], ""]
        if f.get("text"):
            L += ["```text", f["text"], "```"]
        else:
            L.append("*Not extracted: %s. Use the link above.*" % f.get("error", "unknown"))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sam", help="SAM.gov notice id")
    ap.add_argument("--url", help="a direct document URL")
    ap.add_argument("--name", default="document", help="filename for --url")
    ap.add_argument("--title", default="Solicitation documents")
    ap.add_argument("--out", help="write the Drive-ready markdown here")
    ap.add_argument("--list", action="store_true", help="list attachments only")
    a = ap.parse_args()

    if a.sam:
        files = sam_resources(a.sam)
        source = "https://sam.gov/opp/%s/view" % a.sam
    elif a.url:
        files = [{"name": a.name, "size": 0, "id": "", "url": a.url}]
        source = a.url
    else:
        ap.error("need --sam or --url")

    print("%d document(s)" % len(files))
    for f in files:
        print("  %-58s %s" % (f["name"][:58],
                              "%.1f MB" % (f["size"] / 1048576.0) if f["size"] else "?"))
    if a.list:
        return

    for f in files:
        try:
            blob = fetch(f["url"])
        except Exception as e:
            f["text"], f["error"] = "", "download failed: %s" % e
            continue
        if not f["size"]:
            f["size"] = len(blob)
        f["text"], f["error"] = extract(f["name"], blob)
        print("  -> %-40s %s" % (f["name"][:40],
                                 "%d chars" % len(f["text"]) if f["text"] else f["error"]))

    md = render(a.title, source, files)
    if a.out:
        open(a.out, "w", encoding="utf-8", newline="\n").write(md)
        print("\nwrote %s (%d chars, ~%dk tokens)" % (a.out, len(md), len(md) // 4000))
    else:
        sys.stdout.write(md[:3000])


if __name__ == "__main__":
    main()
