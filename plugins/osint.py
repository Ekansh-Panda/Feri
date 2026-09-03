"""Deep OSINT dossier builder plugin."""

import json
import socket
import subprocess
import urllib.parse
import urllib.request
import urllib.error
from typing import Any

from ._template import PLUGIN_DESCRIPTION, PLUGIN_NAME, PLUGIN_VERSION


class OSINTAgent:
    """Deep OSINT dossier builder."""

    def build_dossier(self, target: str) -> dict[str, Any]:
        """Build a comprehensive OSINT dossier for a target."""
        dossier = {
            "target": target,
            "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
            "whois": self.whois(target),
            "dns": self._dns_lookup(target),
            "ssl": self._ssl_info(target),
        }
        if "@" in target:
            email = target
            dossier["breach"] = self.breach_check(email)
            dossier["social"] = self.social_media_search(email.split("@")[0])
        return dossier

    def whois(self, domain: str) -> dict:
        """WHOIS lookup."""
        try:
            import whois
            data = whois.whois(domain)
            return {
                "domain": domain,
                "registrar": getattr(data, "registrar", None),
                "creation_date": str(getattr(data, "creation_date", None)),
                "expiration_date": str(getattr(data, "expiration_date", None)),
                "name_servers": getattr(data, "name_servers", []),
                "emails": getattr(data, "emails", []),
            }
        except ImportError:
            return {"status": "error", "message": "python-whois not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def reverse_ip(self, ip: str) -> dict:
        """Reverse IP lookup."""
        try:
            url = f"https://api.hackertarget.com/reverseiplookup/?q={ip}"
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = resp.read().decode("utf-8")
            return {"status": "success", "ip": ip, "domains": data.strip().splitlines()}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def subdomain_enum(self, domain: str) -> dict:
        """Subdomain enumeration using certificate transparency logs."""
        try:
            url = f"https://crt.sh/?q=%.{domain}&output=json"
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            subdomains = sorted({entry["name_value"] for entry in data})
            return {"status": "success", "domain": domain, "subdomains": subdomains}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def social_media_search(self, name: str) -> dict:
        """Search for social media profiles by name."""
        platforms = {
            "twitter": f"https://twitter.com/{urllib.parse.quote(name)}",
            "github": f"https://github.com/{urllib.parse.quote(name)}",
            "reddit": f"https://reddit.com/user/{urllib.parse.quote(name)}",
            "linkedin": f"https://linkedin.com/search/results/people/?keywords={urllib.parse.quote(name)}",
            "instagram": f"https://instagram.com/{urllib.parse.quote(name)}",
        }
        return {"status": "success", "name": name, "profiles": platforms}

    def breach_check(self, email: str) -> dict:
        """Check Have I Been Pwned for breached accounts."""
        try:
            url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{urllib.parse.quote(email)}"
            req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-NEXUS"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return {"status": "success", "email": email, "breaches": data}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"status": "success", "email": email, "breaches": []}
            return {"status": "error", "code": e.code, "message": e.reason}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def geolocate(self, image_path: str) -> dict:
        """Extract EXIF data and reverse geolocate from an image."""
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS
            img = Image.open(image_path)
            exif = img._getexif()
            if not exif:
                return {"status": "success", "exif": {}}
            exif_data = {}
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                exif_data[tag] = str(value)
            gps_info = self._extract_gps(exif_data)
            return {"status": "success", "exif": exif_data, "gps": gps_info}
        except ImportError:
            return {"status": "error", "message": "Pillow not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _dns_lookup(self, domain: str) -> dict:
        """Basic DNS lookup."""
        try:
            import dns.resolver
            answers = {}
            for record_type in ["A", "MX", "TXT", "NS"]:
                try:
                    answers[record_type] = [str(r) for r in dns.resolver.resolve(domain, record_type)]
                except Exception:
                    answers[record_type] = []
            return {"status": "success", "domain": domain, "records": answers}
        except ImportError:
            try:
                ip = socket.gethostbyname(domain)
                return {"status": "success", "domain": domain, "a": [ip]}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _ssl_info(self, domain: str) -> dict:
        """Get SSL certificate info."""
        try:
            import ssl
            import socket
            context = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
            return {
                "status": "success",
                "subject": dict(x[0] for x in cert.get("subject", ())),
                "issuer": dict(x[0] for x in cert.get("issuer", ())),
                "not_before": cert.get("notBefore"),
                "not_after": cert.get("notAfter"),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _extract_gps(self, exif_data: dict) -> dict:
        """Extract GPS info from EXIF data."""
        try:
            from PIL.ExifTags import GPSTAGS
            gps = {}
            for k, v in exif_data.items():
                if "GPS" in k or "gps" in k:
                    gps[k] = v
            return gps
        except Exception:
            return {}

    def reverse_image_search(self, image_url: str) -> dict:
        """Reverse image search (simulated - would require Google/Bing APIs)."""
        return {
            "status": "success",
            "url": image_url,
            "note": "Reverse image search requires Google/Bing API integration",
            "possible_platforms": [
                "https://images.google.com/searchbyimage?image_url=" + urllib.parse.quote(image_url),
            ],
        }


def get_tools() -> list[dict]:
    return [
        {"name": "build_dossier", "description": "Build comprehensive OSINT dossier.", "parameters": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]}},
        {"name": "whois", "description": "WHOIS lookup.", "parameters": {"type": "object", "properties": {"domain": {"type": "string"}}, "required": ["domain"]}},
        {"name": "reverse_ip", "description": "Reverse IP lookup.", "parameters": {"type": "object", "properties": {"ip": {"type": "string"}}, "required": ["ip"]}},
        {"name": "subdomain_enum", "description": "Subdomain enumeration.", "parameters": {"type": "object", "properties": {"domain": {"type": "string"}}, "required": ["domain"]}},
        {"name": "social_media_search", "description": "Social media search.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
        {"name": "breach_check", "description": "Breach check.", "parameters": {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]}},
        {"name": "geolocate", "description": "Geolocate from EXIF.", "parameters": {"type": "object", "properties": {"image_path": {"type": "string"}}, "required": ["image_path"]}},
    ]


def execute(tool_name: str, params: dict) -> dict:
    instance = OSINTAgent()
    method = getattr(instance, tool_name, None)
    if method and callable(method):
        try:
            return method(**params)
        except TypeError as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    print(json.dumps(execute("breach_check", {"email": "test@example.com"}), indent=2))
