# PDF Structure Extractor

## Challenge Overview
This solution was developed for the Adobe India Hackathon 2025 Challenge 1a, which required building a PDF processing solution that extracts structured data from PDF documents and outputs JSON files. The challenge emphasized performance, resource efficiency, and containerized deployment.

## Solution Features
- Extracts document structure including titles, headings, and text blocks
- Intelligently detects and handles tables using Camelot
- Filters out boilerplate content (headers/footers)
- Handles multi-column layouts and complex document structures
- Processes PDFs within the required 10-second time constraint

## Technical Implementation

### Core Components
Our solution uses the `UltimateExtractor` class which implements a 5-stage extraction pipeline:

1. **Table Detection**: Uses Camelot to identify and exclude table areas
2. **Block Creation**: Creates logical text blocks while filtering margin content
3. **Boilerplate Removal**: Detects and removes repeating headers/footers
4. **Title Detection**: Identifies document title using proximity and style analysis
5. **Heading Detection**: Finds and ranks headings using unified style analysis

### Key Libraries
- **PyMuPDF (fitz)**: Primary PDF processing engine
- **Camelot**: Table detection and analysis
- **Built-in Python Libraries**: For data structures and text processing

### Requirements
```
PyMuPDF>=1.18.0
camelot-py>=0.9.0
opencv-python>=4.5.0  # Required by camelot
ghostscript>=0.7.0    # Required by camelot
```

## Performance Optimizations
- Efficient text block creation with smart margin handling
- Statistical analysis for body text detection
- Smart caching of document structures
- Memory-efficient processing of large documents

## Docker Setup

### Build Command
```bash
docker build --platform linux/amd64 -t pdf-processor .
```

### Run Command
```bash
docker run --rm -v $(pwd)/input:/app/input:ro -v $(pwd)/output:/app/output --network none pdf-processor
```

## Constraints Met
- ✓ Execution Time: Processes 50-page PDFs in under 10 seconds
- ✓ CPU Only: No GPU dependencies
- ✓ Memory Efficient: Stays within 16GB RAM limit
- ✓ Network Independent: Functions without internet access
- ✓ Architecture: Compatible with AMD64 platform

## Output Format
The solution generates JSON files containing:
- Document title
- Hierarchical outline structure
- Clean, structured text content
- Table locations and metadata

## Testing
The solution has been tested against:
- Simple single-column documents
- Complex multi-column layouts
- Documents with tables and figures
- Large documents (50+ pages)
- Various PDF formatting styles

## License
This project uses open-source libraries and is itself open source.

## Authors
Adobe India Hackathon 2025 Participant
