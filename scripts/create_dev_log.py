import os
import sys
import datetime
import argparse

# Configuration
LOG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local_dev_logs")
TEMPLATE_PATH = os.path.join(LOG_ROOT, "templates", "dev_log_template.md")

CATEGORIES = {
    "feature": "feature_logs",
    "bugfix": "bugfix_logs",
    "refactor": "feature_logs", # Refactors often go with features or can be separate
    "docs": "feature_logs"      # Docs treated as features usually
}

def load_template():
    if os.path.exists(TEMPLATE_PATH):
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    else:
        # Fallback template
        return """# [LOG-{date}-{title}] {summary}

## 1. 基础信息 (Metadata)
- **日期 (Date)**: {date_dash}
- **类别 (Category)**: {category}
- **触发原因 (Reason)**: {reason}
- **版本上下文 (Context)**: Branch: main

## 2. 任务背景 (Background)
{background}

## 3. 执行细节 (Execution Details)
{details}

## 4. 技术重点 (Technical Highlights)
{highlights}

## 5. 验证结果 (Verification)
- [ ] 验证点 A
"""

def create_log(title, category, summary="Task Summary", reason="User Request"):
    today = datetime.date.today()
    date_str = today.strftime("%Y%m%d")
    date_dash = today.strftime("%Y-%m-%d")
    
    # Sanitize title
    safe_title = "".join([c if c.isalnum() else "" for c in title])
    if not safe_title:
        safe_title = "Update"
        
    filename = f"LOG-{date_str}-{safe_title}.md"
    
    subdir = CATEGORIES.get(category.lower(), "feature_logs")
    target_dir = os.path.join(LOG_ROOT, subdir)
    
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        
    filepath = os.path.join(target_dir, filename)
    
    if os.path.exists(filepath):
        print(f"Error: File {filepath} already exists.")
        return
        
    template = load_template()
    
    # Simple formatting if template supports it, otherwise raw write
    # Our template uses placeholders like YYYY-MM-DD which are hard to format automatically without regex
    # So we will just replace known headers or prepend/append.
    # Actually, let's use the fallback format logic for reliability if template is complex.
    
    # Let's try to fill the template intelligently
    content = template.replace("YYYY-MM-DD", date_dash)
    content = content.replace("YYYYMMDD", date_str)
    content = content.replace("[ID]", safe_title)
    content = content.replace("任务标题", summary)
    content = content.replace("[Feature | Bugfix | Refactor | Research]", category.title())
    content = content.replace("[用户需求 | 性能优化 | 逻辑修复 | 环境适配]", reason)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Successfully created log file:\n{filepath}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a dev log file.")
    parser.add_argument("title", help="Short CamelCase title for filename (e.g. ReadmeOverhaul)")
    parser.add_argument("--summary", help="Readable title for the document", default="Task Title")
    parser.add_argument("--type", choices=["feature", "bugfix", "refactor", "docs"], default="feature")
    parser.add_argument("--reason", help="Reason for change", default="User Requirement")
    
    args = parser.parse_args()
    
    create_log(args.title, args.type, args.summary, args.reason)
