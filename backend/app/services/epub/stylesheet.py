EINK_STYLESHEET = """
@namespace epub "http://www.idpf.org/2007/ops";

body {
    font-family: Georgia, "Times New Roman", serif;
    line-height: 1.6;
    margin: 4% 3%;
    color: #111111;
    background-color: #ffffff;
}

h1.chapter-title {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 1.75em;
    line-height: 1.25;
    margin-top: 1.2em;
    margin-bottom: 0.3em;
    page-break-before: always;
    break-before: page;
}

.article-meta {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 0.85em;
    color: #444444;
    border-bottom: 1px solid #d1d5db;
    padding-bottom: 0.8em;
    margin-bottom: 1.5em;
}

.article-meta strong {
    color: #111111;
}

p {
    margin-top: 0;
    margin-bottom: 1.1em;
    text-align: justify;
    text-justify: inter-word;
    hyphens: auto;
}

blockquote {
    border-left: 3px solid #6b7280;
    margin: 1.2em 0 1.2em 1.0em;
    padding-left: 0.8em;
    font-style: italic;
    color: #374151;
}

pre, code {
    font-family: "Courier New", Courier, monospace;
    font-size: 0.88em;
    background-color: #f3f4f6;
    border: 1px solid #e5e7eb;
    padding: 0.2em 0.4em;
    border-radius: 3px;
    word-break: break-all;
}

pre {
    padding: 0.8em;
    overflow-x: auto;
    white-space: pre-wrap;
}

img {
    max-width: 100% !important;
    height: auto !important;
    display: block;
    margin: 1.5em auto;
}

figure {
    margin: 1.5em 0;
    text-align: center;
}

figcaption {
    font-size: 0.8em;
    color: #6b7280;
    margin-top: 0.4em;
}

a {
    color: #0284c7;
    text-decoration: underline;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 1.5em 0;
}

th, td {
    border: 1px solid #d1d5db;
    padding: 0.5em;
    text-align: left;
}

th {
    background-color: #f3f4f6;
}
"""
