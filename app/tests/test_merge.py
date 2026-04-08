import os
import shutil
import sys

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.core.exporter import Exporter

class MockClient:
    pass

def test_merge_results():
    test_dir = "test_output"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)

    # Create dummy part files
    with open(os.path.join(test_dir, "part_0.md"), "w") as f:
        f.write("Part 0 content.")
    
    with open(os.path.join(test_dir, "part_1.md"), "w") as f:
        f.write("Part 1 content.")

    exporter = Exporter(MockClient(), test_dir)
    exporter.merge_results()

    full_summary_path = os.path.join(test_dir, "Full_Book_Summary.md")
    assert os.path.exists(full_summary_path)

    with open(full_summary_path, "r") as f:
        content = f.read()
    
    print("Content of Full_Book_Summary.md:")
    print(content)

    # Check for unwanted headers
    assert "## Chapter" not in content
    assert "content.Part 1" not in content # Should have newlines/spacing if not concatenation issues? Actually we added \n\n.
    assert "Part 0 content.\n\nPart 1 content." in content or "Part 0 content.\n\n\n\nPart 1 content." in content # Logic: write content, then \n\n. Loop.

    # Based on my edit:
    # outfile.write(content)
    # outfile.write("\n\n")
    # So part0 + \n\n + part1 + \n\n
    
    expected = "# Full Book Summary\n\nPart 0 content.\n\nPart 1 content.\n\n"
    assert content == expected, f"Expected:\n{repr(expected)}\nGot:\n{repr(content)}"

    print("\nTest Passed!")
    
    # Cleanup
    shutil.rmtree(test_dir)

if __name__ == "__main__":
    test_merge_results()
