#!/usr/bin/env python3
"""Build the public Compose-only DOCX guide for the Akamai SIEM -> Coralogix repo.

Self-contained: only needs python-docx. No internal template or local paths.
"""
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

NAVY = RGBColor(0x02, 0x02, 0x42)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GRAY = RGBColor(0x55, 0x5B, 0x6E)
CODE_BG = "F2F4F8"


def set_cell_bg(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def add_title(doc, text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(20)
    r.font.color.rgb = NAVY
    return p


def add_h1(doc, text):
    p = doc.add_paragraph()
    p.space_before = Pt(14)
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(14)
    r.font.color.rgb = NAVY
    return p


def add_body(doc, text, italic=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(10)
    r.italic = italic
    return p


def add_bullet(doc, text):
    p = doc.add_paragraph(style="List Bullet")
    r = p.add_run(text)
    r.font.size = Pt(10)
    return p


def add_code(doc, text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.name = "Courier New"
    r.font.size = Pt(9)
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), CODE_BG)
    pPr.append(shd)
    return p


def add_table(doc, header, rows):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, h in enumerate(header):
        hdr[i].text = ""
        r = hdr[i].paragraphs[0].add_run(h)
        r.bold = True
        r.font.color.rgb = WHITE
        set_cell_bg(hdr[i], "020242")
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            cells[i].paragraphs[0].add_run(val)
    return t


def main():
    doc = Document()
    add_title(doc, "Akamai SIEM to Coralogix — Docker Compose Deployment")
    add_body(doc, "Collect Akamai SIEM events and forward them to Coralogix for "
                  "the Akamai WAF extension using a single Docker Compose service.", italic=True)

    add_h1(doc, "1. What this does")
    add_code(doc, "Akamai SIEM API\n      |\n      v\n"
                  "akamai-siem pull --emit-datastream   (writes daily NDJSON, saves offset)\n"
                  "      |\n      v\n"
                  "akamai-siem send                     (Coralogix /logs/v1/singles)\n"
                  "      |\n      v\n"
                  "Coralogix app <application> / subsystem <subsystem>")
    add_body(doc, "Native send posts each event in the Coralogix text field, which is "
                  "the shape the Akamai WAF extension parses. No OpenTelemetry collector "
                  "is required.")

    add_h1(doc, "2. Requirements")
    add_bullet(doc, "Docker with Compose v2 (or Podman + native podman-compose).")
    add_bullet(doc, "Akamai SIEM configuration ID.")
    add_bullet(doc, "Akamai .edgerc with SIEM read access.")
    add_bullet(doc, "Coralogix key JSON containing apiKey.keyValue with send-data permission.")
    add_bullet(doc, "linux/amd64 container support (the binary is linux/amd64).")

    add_h1(doc, "3. Repository files")
    add_table(doc, ["File", "Purpose"], [
        ["akamai-siem-linux-amd64", "Prebuilt CLI binary (linux/amd64)"],
        ["SHA256SUMS", "Binary checksum"],
        ["Dockerfile", "Runtime image (binary only, non-root, no secrets)"],
        ["compose.yaml", "Deployment (pull + send loop)"],
        [".env.example", "Non-secret settings + credential file paths"],
    ])

    add_h1(doc, "4. Verify the binary")
    add_code(doc, "sha256sum -c SHA256SUMS\n# akamai-siem-linux-amd64: OK")

    add_h1(doc, "5. Prepare credentials")
    add_code(doc, "chmod 600 /path/to/.edgerc\nchmod 600 /path/to/coralogix-key.json")
    add_body(doc, "Keep both files on the host and never commit them.")

    add_h1(doc, "6. Configure .env")
    add_code(doc, "cp .env.example .env\n# edit: AKAMAI_CONFIG_ID, AKAMAI_EDGERC_FILE,\n"
                  "#       CORALOGIX_DOMAIN, CORALOGIX_APPLICATION,\n"
                  "#       CORALOGIX_SUBSYSTEM, CORALOGIX_KEY_FILE")
    add_body(doc, ".env holds non-secret settings plus the paths to the two credential "
                  "files. Never put the contents of .edgerc or a Coralogix key into it.")

    add_h1(doc, "7. Create runtime directories")
    add_code(doc, "mkdir -p runtime/state runtime/send-state runtime/out\n"
                  "chown -R 100:101 runtime\n"
                  "chmod 700 runtime/state runtime/send-state\n"
                  "chmod 750 runtime/out")
    add_body(doc, "The container runs as UID 100 / GID 101 (akamai).")
    add_table(doc, ["Host dir", "Container path", "Contents"], [
        ["runtime/state", "/var/lib/akamai/state", "Akamai pagination offset"],
        ["runtime/send-state", "/var/lib/akamai/send-state", "Coralogix byte offsets + last-ok"],
        ["runtime/out", "/var/lib/akamai/out", "daily events-YYYYMMDD.ndjson"],
    ])

    add_h1(doc, "8. Start")
    add_code(doc, "docker compose --env-file .env up -d --build")

    add_h1(doc, "9. Logs and health")
    add_code(doc, "docker compose --env-file .env ps          # expect: healthy\n"
                  "docker compose --env-file .env logs -f akamai-siem")
    add_body(doc, "Healthy cycle log output:", italic=True)
    add_code(doc, "done: pages=… … written=… out=/var/lib/akamai/out/events-YYYYMMDD.ndjson\n"
                  "sent: format=datastream events=… file=…\n"
                  "send complete: events=… files=…\n"
                  "cycle ok; sleeping 600s")

    add_h1(doc, "10. Verify delivery with local cx (optional)")
    add_body(doc, "Compose itself does not use the cx CLI. To confirm records are visible, "
                  "query with a cx profile for the same tenant/region:")
    add_code(doc, "cx logs \"source logs | filter $l.applicationname == '<application>' | "
                  "filter $l.subsystemname == '<subsystem>' | limit 10\" \\\n"
                  "  --start now-30m --end now --tier frequent -o json --read-only")
    add_bullet(doc, "Delivery — send requests succeed (see logs).")
    add_bullet(doc, "Visibility — records appear in the query.")
    add_bullet(doc, "Parsing — $d.cx_security.* fields materialize (deployed Akamai WAF extension).")
    add_bullet(doc, "Alerts — the extension's alerts fire on parsed events.")

    add_h1(doc, "11. Restart, stop, upgrade")
    add_code(doc, "docker compose --env-file .env restart\n"
                  "docker compose --env-file .env down      # stop; state preserved")
    add_body(doc, "Upgrade:", italic=True)
    add_code(doc, "docker compose --env-file .env down\n"
                  "# replace akamai-siem-linux-amd64, re-run sha256sum -c SHA256SUMS\n"
                  "docker compose --env-file .env up -d --build")
    add_body(doc, "State is on the host, so restarts resume without re-sending acknowledged data.")

    add_h1(doc, "12. Troubleshooting")
    add_table(doc, ["Symptom", "Likely cause", "Action"], [
        ["Restarts every RETRY_DELAY", "Pull or send failing", "Check docker compose logs"],
        ["401/403 on send", "Key lacks access or wrong team", "Rotate/scope key; check domain"],
        ["Permission denied on out/state", "Bind mounts not owned by 100:101", "Re-run section 7 chown"],
        ["416 offset expired", "Saved cursor too old", "CLI resets to from=now-12h automatically"],
        ["No such image … image not known", "docker-compose shim on Podman", "Use native podman-compose"],
    ])

    add_h1(doc, "13. Security notes")
    add_bullet(doc, "Image contains only the binary; runs as a non-root user.")
    add_bullet(doc, "Credentials mounted read-only as Docker secrets, never baked in.")
    add_bullet(doc, ".env, .edgerc, and the Coralogix key must never be committed.")
    add_bullet(doc, "No customer event data, tenant IDs, or API keys are included.")

    add_h1(doc, "14. Supported architecture")
    add_body(doc, "linux/amd64. The prebuilt binary and image target that platform, "
                  "enforced via platform: linux/amd64 in compose.yaml.")

    out = "/Users/qibal/Documents/soc/akamai/public-repo/Akamai-SIEM-Coralogix-Docker-Compose-Guide.docx"
    doc.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()