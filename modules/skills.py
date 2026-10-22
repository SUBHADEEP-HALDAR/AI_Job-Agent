"""Skill taxonomy: canonical skill names and the aliases that map to them.

Extend SKILL_ALIASES whenever you notice a skill the parser misses.
Aliases are matched case-insensitively on word boundaries, so "java" will not
match inside "javascript" and "sql" will not match inside "mysql".
"""
import re

SKILL_ALIASES = {
    # Programming languages
    "Python": ["python"],
    "SQL": ["sql", "t-sql", "pl/sql", "sqlite"],
    "Java": ["java"],
    "JavaScript": ["javascript", "ecmascript"],
    "TypeScript": ["typescript"],
    "C++": ["c++"],
    "C#": ["c#"],
    "C": ["c programming"],
    # Web
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "React": ["react", "reactjs", "react.js"],
    "Node.js": ["node.js", "nodejs", "node js"],
    "Django": ["django"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi"],
    "Streamlit": ["streamlit"],
    "REST APIs": ["rest api", "rest apis", "restful", "restful api", "restful apis"],
    # Data / ML
    "Excel": ["excel", "ms excel", "microsoft excel", "advanced excel"],
    "Power BI": ["power bi", "powerbi"],
    "Tableau": ["tableau"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "TensorFlow": ["tensorflow"],
    "PyTorch": ["pytorch"],
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning", "neural network", "neural networks"],
    "NLP": ["nlp", "natural language processing"],
    "Statistics": ["statistics", "statistical analysis"],
    "Data Analysis": ["data analysis", "data analytics"],
    "Data Visualization": ["data visualization", "data visualisation",
                           "matplotlib", "seaborn", "plotly"],
    "ETL": ["etl", "data pipeline", "data pipelines"],
    "Spark": ["spark", "pyspark", "apache spark"],
    "Google Analytics": ["google analytics", "ga4"],
    # Databases
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb", "mongo db"],
    # Tools / infra
    "Git": ["git", "github", "gitlab"],
    "Docker": ["docker"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"],
    "Linux": ["linux", "ubuntu", "unix"],
    # QA / process
    "Testing": ["testing", "test cases", "manual testing", "unit testing",
                "quality assurance", "qa"],
    "Selenium": ["selenium"],
    "Agile": ["agile", "scrum"],
    # Design / marketing / business
    "Figma": ["figma"],
    "SEO": ["seo", "search engine optimization"],
    "Digital Marketing": ["digital marketing", "social media marketing"],
    "Content Writing": ["content writing", "copywriting", "blog writing"],
    "Accounting": ["accounting", "bookkeeping", "accounts payable", "gst"],
    "Tally": ["tally", "tally erp", "tally prime"],
    "Customer Support": ["customer support", "customer service", "helpdesk", "help desk"],
    "Communication": ["communication", "communication skills"],
}

_BOUNDARY_L = r"(?<![A-Za-z0-9+#])"
_BOUNDARY_R = r"(?![A-Za-z0-9+#])"


def _compile(alias: str) -> "re.Pattern":
    return re.compile(_BOUNDARY_L + re.escape(alias.lower()) + _BOUNDARY_R)


# canonical -> compiled patterns
_PATTERNS = {
    canon: [_compile(a) for a in aliases] for canon, aliases in SKILL_ALIASES.items()
}
# alias (lowercase) -> canonical
_ALIAS_TO_CANON = {
    a.lower(): canon for canon, aliases in SKILL_ALIASES.items() for a in aliases
}
_ALIAS_TO_CANON.update({c.lower(): c for c in SKILL_ALIASES})


def canon(skill: str) -> str:
    """Map a skill string to its canonical name (or return it cleaned up)."""
    s = (skill or "").strip()
    return _ALIAS_TO_CANON.get(s.lower(), s)


def find_skills(text: str) -> list:
    """Return canonical skills mentioned anywhere in text (taxonomy order)."""
    low = (text or "").lower()
    return [c for c, pats in _PATTERNS.items() if any(p.search(low) for p in pats)]


def mentions(text_lower: str, skill: str) -> bool:
    """True if skill (any alias) appears in already-lowercased text."""
    c = canon(skill)
    pats = _PATTERNS.get(c)
    if pats is None:
        pats = [_compile(c)]
    return any(p.search(text_lower) for p in pats)
