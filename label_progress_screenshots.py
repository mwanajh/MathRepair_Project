from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH


SOURCE = Path(r"C:\Users\mwana\Desktop\MathRepair_Project\MATHREPAIR_SUPERVISOR_PROGRESS_REPORT_CLEAN.docx")
OUTPUT = Path(r"C:\Users\mwana\Desktop\MathRepair_Project\MATHREPAIR_SUPERVISOR_PROGRESS_REPORT_FINAL.docx")


doc = Document(SOURCE)

captions = {
    "python model_pipeline.py --provider mock": (
        "Demonstration screenshot: graph-integrated model trace using the mock provider. "
        "This is a system-validation example, not a benchmark result."
    ),
    "python reasoning_graph.py": (
        "Demonstration screenshot: branching reasoning graph with first-error localization "
        "and selective propagation to affected descendants."
    ),
    "python run_repeated_experiments.py": (
        "Earlier expanded repeated-seed evaluation. This result is separate from the fresh "
        "total-token-matched pilot reported in Section 12."
    ),
}

body = doc.element.body
for child in list(body):
    if not child.tag.endswith("}p"):
        continue
    preceding_text = ""
    previous = child.getprevious()
    if previous is not None:
        preceding_text = "".join(previous.itertext()).strip()
    caption = None
    for command, value in captions.items():
        if preceding_text.startswith(command):
            caption = value
            break
    if caption is None:
        continue

    paragraph = doc.add_paragraph(caption)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.style = "Caption" if "Caption" in [s.name for s in doc.styles] else "Normal"
    for run in paragraph.runs:
        run.italic = True
    child.addnext(paragraph._p)

doc.save(OUTPUT)
print(f"saved {OUTPUT}")
print("added captions: 3")
