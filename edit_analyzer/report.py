"""
HTML report rendering module using Jinja2 templates.
"""

import os
import json
from typing import Union
from jinja2 import Environment, FileSystemLoader
from edit_analyzer.models import AnalysisResult


def render_report(
    result: Union[AnalysisResult, str, dict],
    output_path: str,
    template_dir: str = "templates",
    template_name: str = "report.html.j2",
) -> str:
    """
    Render an AnalysisResult model into a single-file HTML report.
    Accepts AnalysisResult instance, JSON string, or dict, or file path to result.json.
    Writes rendered HTML to output_path and returns the output path.
    """
    if isinstance(result, str):
        if os.path.isfile(result):
            with open(result, "r", encoding="utf-8") as f:
                data = json.load(f)
            analysis_obj = AnalysisResult.model_validate(data)
        else:
            analysis_obj = AnalysisResult.model_validate_json(result)
    elif isinstance(result, dict):
        analysis_obj = AnalysisResult.model_validate(result)
    elif isinstance(result, AnalysisResult):
        analysis_obj = result
    else:
        raise ValueError("Invalid result format passed to render_report")

    # Locate template directory relative to project root or absolute path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    search_dirs = [
        template_dir,
        os.path.join(project_root, template_dir),
        os.path.dirname(template_dir),
    ]

    env = None
    for s_dir in search_dirs:
        if os.path.isdir(s_dir):
            env = Environment(loader=FileSystemLoader(s_dir), autoescape=True)
            break

    if env is None:
        raise FileNotFoundError(f"Template directory '{template_dir}' not found in search paths: {search_dirs}")

    template = env.get_template(template_name)
    html_content = template.render(result=analysis_obj)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_path
