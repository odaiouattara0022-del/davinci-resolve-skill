#!/usr/bin/env python3
"""Build the mindmap catalog consumed by index.html.

Reads the file tree of the Ignitetechnologies/Mindmap repository and emits a
compact JSON catalog (one entry per mindmap, with its image variants, PDF and
category). The catalog is written to catalog.json and injected into index.html
between the CATALOG markers so the viewer stays a single standalone file.

Usage:
    python3 build_catalog.py --repo /path/to/Mindmap-clone
    python3 build_catalog.py --file-list files.txt     # one repo-relative path per line
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))

IMAGE_RE = re.compile(r"^(?P<base>.*?)(?:\s+(?P<q>UHD|HD Normal|HD|Normal))?\.(?P<ext>png|jpe?g)$", re.I)
QUALITY_ALIASES = {"hd normal": "Normal"}

# Directory -> thematic category. Unlisted directories fall back to "Divers".
CATEGORIES = [
    ("Active Directory", [
        "AD Enumeration", "AD Pentest", "Crackmapexec", "NXC", "Impacket",
        "Mimikatz", "Empire", "HTB/Bloodhound", ".:Active Directory Pentesting",
        ".:SMB Enumeration",
    ]),
    ("Reconnaissance & OSINT", [
        "OSINT", "Shodan", "Censys", "Google Dorks", "Github Dorks",
        "Google Search Operators", "Red Team Dorks", "Serach Engine for Pentester",
        "Subdomain Enumeration", "Enumeration", "Nmap", "Other",
        ".:privacy Search Engine",
    ]),
    ("Web & applications", [
        "Owasp", "Burp Suite", "Sqlmap", "XSS Tools", "SSRF Tools", "ffuf",
        "gobuster", "Feroxbuster", "wfuzz", "wpscan", "httpx", "HTTP Status Code",
        "Web App Docker", "HTB/Web", "Vulnerability Scanners",
        ".:Burpsuite", ".:Web Directory Scanners",
    ]),
    ("Post-exploitation & privesc", [
        "Linux Privs", "Windows Privs", "Windows Privileges", "Gtfobin", "Vulnhub",
        "Metasploit", "HTB/Tunneling", ".:Privs Tools",
    ]),
    ("Mots de passe & cracking", [
        "hashcat", "John", "hydra", "medusa", ".:Wordlists Generator",
    ]),
    ("Réseau & wireless", [
        "Wireshark", "Tshark", "Tcpdump", "ICMP", "Wireless Pentest Tools", "aircrack",
    ]),
    ("Red Team & menaces", [
        "Red Teaming", "Social Engineering", "Mitre Attack", "Cyber Security Attack",
        "Ransomware", "Cyber Hack", "Zero-Day CVEs (2023)",
    ]),
    ("Blue Team & forensics", [
        "Blue Team", "Forensics", "Security Automation", "Tools/Defensive", "IDAPro",
    ]),
    ("Cloud, DevOps & conteneurs", [
        "Cloud Security Framework", "Container Security", "Docker CheatSheet", "Devops",
    ]),
    ("Gouvernance & conformité", [
        "GDPR", "HIPPA", "FISMA", "ISO Control", "SOC 2", "nist", "Security 360",
        "Cybersec Technologies",
    ]),
    ("Apprentissage & certifications", [
        "HTB", "TryHackMe", ".:OSCP Practice Tools",
    ]),
    ("Outils & confidentialité", [
        "Tools", "Tools/Offensive Security", "Firefox Pentest Addons", "Privacy Tools",
        ".:Privacy Email Accounts",
    ]),
]

# Extra search keywords per category, so a French query finds English titles.
CATEGORY_KEYWORDS = {
    "Active Directory": "ad kerberos ldap domaine domain controller bloodhound smb",
    "Reconnaissance & OSINT": "recon reconnaissance osint scan dorks moteur recherche enumeration",
    "Web & applications": "web http api xss sqli injection fuzzing bug bounty",
    "Post-exploitation & privesc": "privilege escalation elevation privileges pivot tunneling shell",
    "Mots de passe & cracking": "password hash bruteforce brute force wordlist mot de passe",
    "Réseau & wireless": "network reseau wifi wireless paquets packets sniffing capture",
    "Red Team & menaces": "attaque attack adversaire ttp mitre ransomware phishing cve",
    "Blue Team & forensics": "defense defensive soc detection incident investigation malware",
    "Cloud, DevOps & conteneurs": "cloud aws azure gcp docker kubernetes ci cd pipeline",
    "Gouvernance & conformité": "compliance conformite norme standard audit rgpd risque",
    "Apprentissage & certifications": "training formation ctf lab certification exam",
    "Outils & confidentialité": "tools outils vie privee privacy anonymat addons",
    "Divers": "",
}

# Files that are not mindmaps (repository banner, placeholders...).
EXCLUDE = {"mind.jpg"}

# Titles that need a friendlier label than the raw filename.
TITLE_FIXES = {
    "HTB": "HTB Web Cheat Sheet",
    "ATTCK Matrix": "ATT&CK Matrix (Enterprise)",
    "SOC 2": "SOC 2",
    "Offensive_Linux_Security_Tools": "Offensive Linux Security Tools",
    "mind": "Mindmap",
    "Web Lab Docker": "Web Pentest Lab (Docker)",
    "Vulnhub Privs Cheatsheet": "Vulnhub Privilege Escalation",
}

QUALITY_ORDER = ["Normal", "HD", "UHD"]


def norm(text):
    """Aggressive normalisation used for fuzzy matching between names."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", text)


def slugify(text):
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower())
    return text.strip("-") or "map"


def category_for(directory, title):
    key = directory or "."
    explicit = "{}:{}".format(key, title)
    for name, members in CATEGORIES:
        if explicit in members:
            return name
    for name, members in CATEGORIES:
        if key in members:
            return name
    # A sub-directory inherits its parent's category when possible.
    if "/" in key:
        parent = key.split("/")[0]
        for name, members in CATEGORIES:
            if parent in members:
                return name
    return "Divers"


def read_file_list(args):
    if args.file_list:
        with open(args.file_list, encoding="utf-8") as handle:
            return [line.strip() for line in handle if line.strip()]
    paths = []
    root = os.path.abspath(args.repo)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            full = os.path.join(dirpath, name)
            paths.append(os.path.relpath(full, root).replace(os.sep, "/"))
    return sorted(paths)


def match_pdf(title, pdfs, single_group):
    """Pick the PDF of the directory that belongs to this mindmap."""
    if not pdfs:
        return None
    if len(pdfs) == 1 and single_group:
        return pdfs[0]
    target = norm(title)
    best, best_score = None, 0.0
    for pdf in pdfs:
        base = norm(os.path.splitext(os.path.basename(pdf))[0])
        if base == target:
            return pdf
        if base.startswith(target) or target.startswith(base):
            score = 0.9
        else:
            shared = len(set(re.findall(r"[a-z0-9]{3,}", base)) &
                         set(re.findall(r"[a-z0-9]{3,}", target)))
            total = max(1, len(set(re.findall(r"[a-z0-9]{3,}", target))))
            score = 0.6 * shared / total
        if score > best_score:
            best, best_score = pdf, score
    if best_score >= 0.5:
        return best
    return pdfs[0] if single_group else None


def build(paths):
    groups = OrderedDict()
    pdfs_by_dir = OrderedDict()

    for path in paths:
        directory, _, name = path.rpartition("/")
        if name in EXCLUDE or path in EXCLUDE:
            continue
        lower = name.lower()
        if lower.endswith(".pdf"):
            pdfs_by_dir.setdefault(directory, []).append(path)
            continue
        match = IMAGE_RE.match(name)
        if not match:
            continue  # README, placeholder files, anything unexpected
        base = match.group("base").strip()
        quality = match.group("q") or "Normal"
        quality = QUALITY_ALIASES.get(quality.lower(), quality)
        key = (directory, norm(base))
        group = groups.get(key)
        if group is None:
            group = {"dir": directory, "title": base, "images": {}}
            groups[key] = group
        elif len(base) > len(group["title"]):
            group["title"] = base
        group["images"][quality] = path

    per_dir = {}
    for directory, _ in groups:
        per_dir[directory] = per_dir.get(directory, 0) + 1

    entries = []
    used_slugs = set()
    for (directory, _), group in groups.items():
        raw_title = group["title"].replace("_", " ").strip()
        title = TITLE_FIXES.get(group["title"], TITLE_FIXES.get(raw_title, raw_title))
        title = re.sub(r"\s+", " ", title)
        category = category_for(directory, group["title"])

        slug = slugify(title)
        if slug in used_slugs:
            slug = slugify("{}-{}".format(directory or "root", title))
        n = 2
        while slug in used_slugs:
            slug = "{}-{}".format(slugify(title), n)
            n += 1
        used_slugs.add(slug)

        pdf = match_pdf(group["title"], pdfs_by_dir.get(directory, []),
                        per_dir.get(directory, 0) == 1)

        images = OrderedDict()
        for quality in QUALITY_ORDER:
            if quality in group["images"]:
                images[quality] = group["images"][quality]

        entries.append(OrderedDict([
            ("slug", slug),
            ("title", title),
            ("category", category),
            ("dir", directory),
            ("images", images),
            ("pdf", pdf),
            ("keywords", " ".join(filter(None, [
                directory.replace("/", " "),
                CATEGORY_KEYWORDS.get(category, ""),
            ]))),
        ]))

    entries.sort(key=lambda e: (e["category"].lower(), e["title"].lower()))

    order = [name for name, _ in CATEGORIES] + ["Divers"]
    present = [c for c in order if any(e["category"] == c for e in entries)]

    return OrderedDict([
        ("source", OrderedDict([
            ("repo", "Ignitetechnologies/Mindmap"),
            ("branch", "main"),
            ("url", "https://github.com/Ignitetechnologies/Mindmap"),
        ])),
        ("categories", present),
        ("maps", entries),
    ])


def inject(catalog, html_path):
    if not os.path.exists(html_path):
        return False
    with open(html_path, encoding="utf-8") as handle:
        html = handle.read()
    start = "/* CATALOG:START */"
    end = "/* CATALOG:END */"
    if start not in html or end not in html:
        return False
    payload = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    head, rest = html.split(start, 1)
    _, tail = rest.split(end, 1)
    with open(html_path, "w", encoding="utf-8") as handle:
        handle.write("{}{}\nconst CATALOG = {};\n{}{}".format(head, start, payload, end, tail))
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", help="path to a clone of Ignitetechnologies/Mindmap")
    parser.add_argument("--file-list", help="text file with one repo-relative path per line")
    parser.add_argument("--out", default=os.path.join(HERE, "catalog.json"))
    parser.add_argument("--html", default=os.path.join(HERE, "index.html"))
    args = parser.parse_args()

    if not args.repo and not args.file_list:
        parser.error("pass --repo or --file-list")

    catalog = build(read_file_list(args))
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(catalog, handle, ensure_ascii=False, indent=1)
        handle.write("\n")

    injected = inject(catalog, args.html)
    print("{} mindmaps, {} catégories -> {}".format(
        len(catalog["maps"]), len(catalog["categories"]), args.out))
    print("index.html {}".format("mis à jour" if injected else "non modifié (marqueurs absents)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
