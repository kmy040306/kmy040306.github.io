"""실행·검토한 최종 노트북을 GitHub Pages 첫 화면으로 내보냅니다."""
from pathlib import Path
from nbconvert import HTMLExporter
import nbformat

root = Path(__file__).resolve().parents[1]
notebook = nbformat.read(root / "final/tutorial.ipynb", as_version=4)
nbformat.validate(notebook)
html, _ = HTMLExporter().from_notebook_node(notebook)
(root / "index.html").write_text(html, encoding="utf-8")
print("Exported index.html (노트북 실행은 별도로 수행하세요)")
