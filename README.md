# XLIFF AI Assistant

XLIFF AI Assistant is a professional desktop tool designed to help translators work with XLIFF files more efficiently using AI.

It combines the structure of standard CAT (Computer-Assisted Translation) tools with the power of Large Language Models (LLMs).

## Features

*   **Desktop Application**: Built with Python and PyQt6 for a fast, native experience.
*   **Tag Protection**: Intelligently abstracts XML tags (e.g., `<bpt id="1">`) to prevent AI from messing up the file structure.
*   **AI Integration**: Supports OpenAI, SiliconFlow, DeepSeek, and more.
*   **Interactive Refinement**: Select any segment and ask AI to "Make it shorter", "Fix grammar", or any custom instruction.
*   **Batch Processing**: Translate thousands of segments automatically.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-username/xliff-ai-assistant.git
    cd xliff-ai-assistant
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

### Option 1: Run from Source (Recommended for Developers)

Simply run the Python script:

```bash
python desktop_app.py
```

### Option 2: Run the Executable (Recommended for Users)

If you have downloaded the `.exe` version:
1.  Double-click `XLIFF_AI_Assistant.exe`.
2.  No Python installation required.

## Development Guide

### Project Structure

*   `desktop_app.py`: Main entry point for the GUI application.
*   `core/`: Contains logic for XLIFF parsing and tag handling.
*   `ai/`: Contains the LLM client wrapper.

### Building the Executable

To build a standalone `.exe` file using the included spec file:

```bash
pip install pyinstaller
pyinstaller XLIFF_AI_Assistant.spec
```

The output file will be in the `dist/` folder.

## License

MIT
