"""Run isolated TXT/PDF/DOCX ingestion, semantic search and frozen generation."""
import argparse
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from evidence_api.document_e2e import run_suite


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default=str(ROOT/'results'))
    args=parser.parse_args()
    from ollama import Client
    result,bundle=run_suite(ROOT,args.output,Client(host=os.environ.get('OLLAMA_HOST','http://localhost:11434'),timeout=180.0))
    if result.get('fatal_error') or result.get('format_errors') or not result['all_expected_answer_records_present']:
        raise SystemExit(1)

if __name__=='__main__':main()
