import argparse
import os
import sys
from core.parser import XliffParser
from core.abstractor import TagAbstractor
from core.validator import Validator
from ai.client import LLMClient

def main():
    parser = argparse.ArgumentParser(description="XLIFF AI Assistant")
    parser.add_argument("input_file", help="Path to input .xlf file")
    parser.add_argument("--source-lang", default="en", help="Source language code")
    parser.add_argument("--target-lang", default="zh-CN", help="Target language code")
    parser.add_argument("--output", help="Path to output .xlf file")
    
    args = parser.parse_args()
    
    input_path = args.input_file
    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        sys.exit(1)
        
    print(f"Loading {input_path}...")
    xliff_parser = XliffParser(input_path)
    xliff_parser.load()
    units = xliff_parser.get_translation_units()
    print(f"Found {len(units)} translation units.")
    
    # Abstraction
    abstractor = TagAbstractor()
    segments_to_translate = []
    
    print("Abstracting tags...")
    for u in units:
        if u.state == "translated":
            continue # Skip already translated
            
        res = abstractor.abstract(u.source_raw)
        u.source_abstracted = res.abstracted_text
        u.tags_map = res.tags_map
        
        segments_to_translate.append({
            "id": u.id,
            "text": u.source_abstracted
        })
        
    if not segments_to_translate:
        print("No new segments to translate.")
        sys.exit(0)
        
    # AI Translation
    print(f"Translating {len(segments_to_translate)} segments with AI...")
    client = LLMClient(provider="mock")
    results = client.translate_batch(segments_to_translate, args.source_lang, args.target_lang)
    
    # Map results back
    results_map = {r["id"]: r["translation"] for r in results}
    
    # Validation & Reconstruction
    validator = Validator()
    success_count = 0
    errors_count = 0
    
    print("Validating and reconstructing...")
    for u in units:
        if u.id in results_map:
            translation = results_map[u.id]
            u.target_abstracted = translation
            
            # Valdiate
            errors = validator.validate_structure(u)
            if errors:
                print(f"[Warn] Unit {u.id} has errors: {errors}")
                errors_count += 1
                # Strategy: If critical error, maybe don't save target? 
                # For MVP, we save but log warning.
            
            # Reconstruct
            try:
                u.target_raw = abstractor.reconstruct(u.target_abstracted, u.tags_map)
                u.state = "translated"
                success_count += 1
            except Exception as e:
                print(f"[Error] Failed to reconstruct Unit {u.id}: {e}")
                errors_count += 1
    
    # Save
    output_path = args.output or input_path.replace(".xlf", "_ai.xlf")
    print(f"Saving to {output_path}...")
    xliff_parser.update_targets(units, output_path)
    
    print(f"Done. Success: {success_count}, Errors: {errors_count}")

if __name__ == "__main__":
    main()
