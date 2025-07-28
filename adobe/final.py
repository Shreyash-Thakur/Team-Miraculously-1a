import fitz 
import camelot
import json
import collections
import re
import statistics

class UltimateExtractor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self.blocks = []
        self.title = ""
        self.outline = []

    def run(self):
        """Executes the full extraction pipeline."""
        table_areas = self._detect_tables()
        self._create_blocks(table_areas)
        self._detect_and_filter_boilerplate()
        self._find_title()
        self._find_headings()
        self.doc.close()
        return {"title": self.title, "outline": self.outline}

    def _detect_tables(self):
        """Uses Camelot to find all table areas in the PDF."""
        print("Stage 1: Detecting table areas with Camelot...")
        try:
            tables = camelot.read_pdf(self.pdf_path, pages='all', flavor='lattice', line_scale=40, suppress_stdout=True)
        except Exception:
            tables = []
        
        table_areas = collections.defaultdict(list)
        for table in tables:
            page = self.doc[table.page - 1]
            page_height = page.rect.height
            x1, y1, x2, y2 = table._bbox
            table_rect = fitz.Rect(x1, page_height - y2, x2, page_height - y1)
            table_areas[table.page - 1].append(table_rect)
        print(f"  Found {len(tables)} table areas to exclude.")
        return table_areas

    def _create_blocks(self, table_areas):
        """
        Creates logical text blocks, ignoring tables and text in the page margins.
        """
        print("Stage 2: Creating logical text blocks and ignoring margins...")
        for page_num, page in enumerate(self.doc):
            page_table_bboxes = table_areas.get(page_num, [])
            
            # FINAL FIX: Define a content area to ignore vertical text in margins
            page_width = page.rect.width
            margin_x0 = page_width * 0.10  # 10% margin from the left
            margin_x1 = page_width * 0.90  # 10% margin from the right

            chars = []
            blocks_raw = page.get_text("rawdict")["blocks"]
            for b in blocks_raw:
                if 'lines' in b:
                    for l in b['lines']:
                        for s in l['spans']:
                            for c in s['chars']:
                                char_rect = fitz.Rect(c['bbox'])
                                is_in_table = any(char_rect.intersects(bbox) for bbox in page_table_bboxes)
                                
                                # Check if character is within the central content area
                                is_in_margin = c['bbox'][0] < margin_x0 or c['bbox'][2] > margin_x1
                                
                                if not is_in_table and not is_in_margin and c['c'].strip():
                                    c['font'] = s['font']
                                    c['size'] = s['size']
                                    chars.append(c)
            
            if not chars: continue

            lines = collections.defaultdict(list)
            for char in sorted(chars, key=lambda c: (c['bbox'][1], c['bbox'][0])):
                y0 = round(char['bbox'][1])
                found_line = False
                for y_key in lines:
                    if abs(y_key - y0) < 2:
                        lines[y_key].append(char)
                        found_line = True
                        break
                if not found_line:
                    lines[y0].append(char)

            for y0 in sorted(lines.keys()):
                line_chars = sorted(lines[y0], key=lambda c: c['bbox'][0])
                if not line_chars: continue

                full_text = ""
                for i, char_info in enumerate(line_chars):
                    full_text += char_info['c']
                    if i < len(line_chars) - 1:
                        next_char_info = line_chars[i+1]
                        gap = next_char_info['bbox'][0] - char_info['bbox'][2]
                        if gap > 1.0:
                            full_text += " "
                
                first_char = line_chars[0]
                last_char = line_chars[-1]
                self.blocks.append({
                    'text': full_text.strip(), 'size': first_char['size'], 'font': first_char['font'],
                    'page': page_num, 'bbox': fitz.Rect(first_char['bbox'][0], first_char['bbox'][1], last_char['bbox'][2], last_char['bbox'][3])
                })

    def _detect_and_filter_boilerplate(self):
        """Finds and filters repeating headers/footers using a signature method."""
        print("Stage 3: Detecting and filtering boilerplate text...")
        signatures = collections.Counter()
        for block in self.blocks:
            sig = f"{block['text']}|{round(block['size'])}|{round(block['bbox'].x0 / 10)}"
            signatures[sig] += 1
        
        repeat_threshold = max(2, int(self.doc.page_count * 0.25))
        boilerplate_sigs = {sig for sig, count in signatures.items() if count >= repeat_threshold}
        
        self.blocks = [
            block for block in self.blocks 
            if f"{block['text']}|{round(block['size'])}|{round(block['bbox'].x0 / 10)}" not in boilerplate_sigs
        ]

    def _find_title(self):
        """Finds the title using proximity and style."""
        print("Stage 4: Finding the document title...")
        first_page_blocks = [b for b in self.blocks if b['page'] == 0]
        if not first_page_blocks: return

        page_height = self.doc[0].rect.height
        top_blocks = [b for b in first_page_blocks if b['bbox'].y0 < page_height * 0.5]
        if not top_blocks: return

        try:
            anchor_block = max(top_blocks, key=lambda x: x['size'])
            title_lines = [anchor_block]
            for block in top_blocks:
                if block['text'] == anchor_block['text']: continue
                is_large = block['size'] >= anchor_block['size'] * 0.75
                is_close = abs(block['bbox'].y0 - anchor_block['bbox'].y0) < page_height * 0.1
                if is_large and is_close:
                    title_lines.append(block)
            
            title_lines.sort(key=lambda x: x['bbox'].y0)
            self.title = " ".join(line['text'] for line in title_lines)
        except ValueError:
            self.title = ""

    def _find_headings(self):
        """Finds headings using a unified, prioritized logic and then ranks them by style."""
        print("Stage 5: Finding and ranking headings...")
        potential_headings = []
        
        if self.blocks:
            font_sizes = [round(b['size']) for b in self.blocks]
            try:
                body_size = statistics.mode(font_sizes)
            except statistics.StatisticsError:
                body_size = collections.Counter(font_sizes).most_common(1)[0][0] if font_sizes else 10
        else:
            body_size = 10
        print(f"  Detected body text font size: {body_size}")

        for i, block in enumerate(self.blocks):
            text = block['text'].strip()
            font_size = round(block['size'])
            if not text or (self.title and text in self.title): continue
            if '....' in text: continue

            is_numbered = re.match(r'^\s*(\d+(\.\d+)*\.?)\s*', text)
            
            if is_numbered and font_size > body_size:
                style_key = (font_size, block['font'])
                block['style'] = style_key
                potential_headings.append(block)
                continue

            is_bold = 'bold' in block['font'].lower()
            is_bigger = font_size > body_size * 1.15
            
            has_space_below = False
            if i + 1 < len(self.blocks) and block['page'] == self.blocks[i+1]['page']:
                vertical_gap = self.blocks[i+1]['bbox'].y0 - block['bbox'].y1
                line_height = block['bbox'].y1 - block['bbox'].y0 if block['bbox'].y1 > block['bbox'].y0 else 1
                if vertical_gap > (line_height * 0.5):
                    has_space_below = True
            
            if (is_bold and is_bigger) or (has_space_below and font_size > body_size):
                style_key = (font_size, block['font'])
                block['style'] = style_key
                potential_headings.append(block)

        headings_by_style = collections.defaultdict(list)
        for h in potential_headings:
            headings_by_style[h['style']].append(h)
        
        unique_styles = sorted(list(headings_by_style.keys()), key=lambda x: x[0], reverse=True)
        style_to_level = {style: f"H{i+1}" for i, style in enumerate(unique_styles)}

        outline_temp = []
        for h in potential_headings:
            level = style_to_level.get(h['style'])
            if level:
                if int(level[1:]) <= 4:
                    outline_temp.append({"level": level, "text": h['text'], "page": h['page'], "bbox": h['bbox']})
        
        final_outline_with_bbox = list({(item['text'], item['page']): item for item in outline_temp}.values())
        final_outline_with_bbox.sort(key=lambda x: (x['page'], x['bbox'].y0))
        self.outline = [
            {"level": item["level"], "text": item["text"], "page": item["page"] + 1}
            for item in final_outline_with_bbox
        ]
        if not self.title and self.outline:
            h1s = [h for h in self.outline if h['level'] == 'H1']
            self.title = h1s[0]['text'] if h1s else ''

# --- Main execution block ---
if __name__ == "__main__":
    from pathlib import Path
    import os

    # Define the input and output directories
    INPUT_DIR = Path("/app/input")
    OUTPUT_DIR = Path("/app/output")

    # Ensure the output directory exists.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Find all PDF files in the input directory.
    pdf_files = list(INPUT_DIR.glob("*.pdf"))

    if not pdf_files:
        print("No PDF files found in /app/input directory.")
    else:
        print(f"Found {len(pdf_files)} PDF(s) to process.")

    # Loop through each PDF file and process it.
    for pdf_path in pdf_files:
        print(f"\n--- Analyzing '{pdf_path.name}' ---")
        
        # Construct the corresponding output path.
        output_json_path = OUTPUT_DIR / f"{pdf_path.stem}.json"

        try:
            # Initialize and run the extractor for the current PDF.
            extractor = UltimateExtractor(str(pdf_path))
            document_structure = extractor.run()
            
            # Save the output to a JSON file.
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(document_structure, f, indent=4)
                
            print(f"Successfully saved outline to '{output_json_path}'")

        except Exception as e:
            # If an error occurs, print it and create an empty JSON file as a fallback.
            print(f"!! An error occurred while processing {pdf_path.name}: {e}")
            error_output = {"title": "", "outline": [], "error": str(e)}
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(error_output, f, indent=4)

    print("\n--- All files processed. ---")