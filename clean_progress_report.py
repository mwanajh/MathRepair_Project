from pathlib import Path
from docx import Document


SOURCE = Path(r"C:\Users\mwana\Desktop\MathRepair_Project\MATHREPAIR_SUPERVISOR_PROGRESS_REPORT.docx")
OUTPUT = Path(r"C:\Users\mwana\Desktop\MathRepair_Project\MATHREPAIR_SUPERVISOR_PROGRESS_REPORT_CLEAN.docx")


doc = Document(SOURCE)

# Keep commands that reproduce the methodology and measured experiments.
# The web-server launch and the older interactive prototype are not needed in
# the main progress report; their screenshots are removed below as well.
commands_to_remove = {
    "python graph_web_server.py --port 8765",
    "python mathrepair_demo.py",
}
for paragraph in list(doc.paragraphs):
    if paragraph.text.strip() in commands_to_remove:
        element = paragraph._element
        element.getparent().remove(element)

# Align the branching-graph description with the current command output.
old_description = (
    "For the pipeline demonstration 2(x + 3) = 14, n1 stores the problem state, "
    "n2 stores the model's invalid 2x + 3 = 14 transformation, and n3-n4 are affected descendants. "
    "The graph records REFORMALIZE, the repaired state 2x + 6 = 14, recomputed x = 4, and final node statuses. "
    "A separate branching fixture retains an independent valid branch to test selective descendant propagation "
    "and zero allocation to unaffected nodes."
)
new_description = (
    "For the branching demonstration 2(x + 3) = 14, n1 stores the model's invalid 2x + 3 = 14 transformation, "
    "n2-n3 are affected descendants, and n4-n5 form an independent valid branch. The graph records REFORMALIZE, "
    "the repaired state 2x + 6 = 14, recomputed x = 4, and final node statuses. This structure tests selective "
    "descendant propagation and zero allocation to unaffected nodes."
)
for paragraph in doc.paragraphs:
    if paragraph.text.strip() == old_description:
        paragraph.text = new_description
        break
else:
    raise RuntimeError("Could not find the branching-graph description paragraph")

old_deliverable = "Reasoning-graph command-line and graphical web demonstrations."
new_deliverable = "Reasoning-graph command-line demonstration with a retained graphical web view."
for paragraph in doc.paragraphs:
    if paragraph.text.strip() == old_deliverable:
        paragraph.text = new_deliverable
        break
else:
    raise RuntimeError("Could not find the web-demo deliverable paragraph")

# Remove the two screenshot paragraphs tied to the deleted commands while
# retaining the package media metadata so Word can open the document cleanly.
BLIP = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
EMBED = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
removed_image_paragraphs = 0
for child in list(doc.element.body):
    if not child.tag.endswith("}p"):
        continue
    remove = False
    for blip in child.iter(BLIP):
        rel_id = blip.get(EMBED)
        if not rel_id or rel_id not in doc.part.rels:
            continue
        target = doc.part.rels[rel_id].target_ref.replace("\\", "/")
        if target in {"media/image1.png", "media/image2.png"}:
            remove = True
            break
    if remove:
        child.getparent().remove(child)
        removed_image_paragraphs += 1

doc.save(OUTPUT)

print(f"saved {OUTPUT}")
print("removed commands: graph_web_server.py, mathrepair_demo.py")
print(f"removed screenshot paragraphs: {removed_image_paragraphs}")
