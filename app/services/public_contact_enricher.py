import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException, SSLError
from requests.utils import requote_uri


@dataclass(slots=True)
class EnrichedContact:
    website: str
    contact_source_url: str
    email: str | None
    phone: str | None


class PublicContactEnricher:
    search_endpoint = "https://html.duckduckgo.com/html/"
    bing_search_endpoint = "https://www.bing.com/search"
    user_agent = "MarketInsightOfficer/0.1 (+https://local.dev)"
    yellowpages_search_endpoint = "https://www.yellowpages.com.vn/search.asp"
    gelbeseiten_search_endpoint = "https://www.gelbeseiten.de/suche"
    ignored_domains = {
        "facebook.com",
        "www.facebook.com",
        "linkedin.com",
        "www.linkedin.com",
        "zoominfo.com",
        "www.zoominfo.com",
        "dnb.com",
        "www.dnb.com",
        "go4worldbusiness.com",
        "www.go4worldbusiness.com",
        "ec21.com",
        "www.ec21.com",
        "exporthub.com",
        "www.exporthub.com",
        "vnbis.com",
        "www.vnbis.com",
    }
    directory_domains = {
        "gelbeseiten.de",
        "www.gelbeseiten.de",
        "yellowpages.com.vn",
        "www.yellowpages.com.vn",
        "yellowpages.vn",
        "www.yellowpages.vn",
        "yellowpages.com",
        "www.yellowpages.com",
        "yellowpages-uae.com",
        "www.yellowpages-uae.com",
        "connect.ae",
        "www.connect.ae",
    }
    social_domains = {
        "facebook.com",
        "www.facebook.com",
        "linkedin.com",
        "www.linkedin.com",
        "instagram.com",
        "www.instagram.com",
        "x.com",
        "www.x.com",
        "twitter.com",
        "www.twitter.com",
        "youtube.com",
        "www.youtube.com",
        "wa.me",
        "www.wa.me",
    }
    contact_keywords = {
        "contact",
        "contact-us",
        "contactus",
        "lien-he",
        "lienhe",
        "lien_he",
        "kontakt",
        "impressum",
        "about-us",
    }
    email_pattern = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
    phone_pattern = re.compile(r"\+?\d[\d\s()./-]{7,}\d")
    country_dialing_codes = {
        "germany": "+49",
        "united arab emirates": "+971",
        "united states": "+1",
        "vietnam": "+84",
        "viet nam": "+84",
    }
    noisy_email_markers = {
        "yellowpages",
        "facebook",
        "zoominfo",
        "dnb",
        "go4worldbusiness",
    }

    def __init__(self, *, timeout_seconds: int = 12) -> None:
        self.timeout_seconds = timeout_seconds
        self._cache: dict[tuple[str, str], EnrichedContact | None] = {}

    def enrich(self, *, company_name: str, country: str) -> EnrichedContact | None:
        normalized_country = country.strip().lower()
        cache_key = (company_name.strip().lower(), normalized_country)
        if cache_key in self._cache:
            return self._cache[cache_key]

        matchers = {
            "vietnam": self._enrich_vietnam,
            "viet nam": self._enrich_vietnam,
            "germany": self._enrich_germany,
            "australia": self._enrich_australia,
            "united arab emirates": self._enrich_uae,
        }
        matcher = matchers.get(normalized_country)
        if matcher:
            match = matcher(company_name=company_name, country=country)
            self._cache[cache_key] = match
            return match

        match = self._enrich_via_public_search(company_name=company_name, country=country)
        self._cache[cache_key] = match
        return match

    def _enrich_vietnam(self, *, company_name: str, country: str) -> EnrichedContact | None:
        best_match: EnrichedContact | None = None
        best_score = -1
        for keyword in self._company_keywords(company_name):
            listing_url = self._lookup_vietnam_yellowpages(keyword)
            if not listing_url:
                continue
            enriched = self._extract_from_page(listing_url, country=country)
            if not enriched:
                continue
            score = self._contact_score(enriched) + 15
            if score > best_score:
                best_match = enriched
                best_score = score
        return best_match

    def _enrich_germany(self, *, company_name: str, country: str) -> EnrichedContact | None:
        best_match: EnrichedContact | None = None
        best_score = -1
        for keyword in self._company_keywords(company_name):
            for listing_url in self._lookup_germany_gelbeseiten(keyword):
                enriched = self._extract_from_page(listing_url, country=country)
                if not enriched:
                    continue
                score = self._contact_score(enriched) + 12
                if score > best_score:
                    best_match = enriched
                    best_score = score
        if best_match:
            return best_match
        return self._enrich_via_public_search(
            company_name=company_name,
            country=country,
            extra_queries=['site:gelbeseiten.de/gsbiz'],
        )

    def _enrich_uae(self, *, company_name: str, country: str) -> EnrichedContact | None:
        return self._enrich_via_public_search(
            company_name=company_name,
            country=country,
            extra_queries=[
                'site:yellowpages-uae.com',
                'site:connect.ae',
            ],
        )

    def _enrich_australia(self, *, company_name: str, country: str) -> EnrichedContact | None:
        best_match: EnrichedContact | None = None
        best_score = -1

        for hint_url in self._lookup_australia_contact_hints(company_name):
            enriched = self._extract_from_page(hint_url, country=country)
            if not enriched:
                continue
            score = self._contact_score(enriched) + 30
            if score > best_score:
                best_match = enriched
                best_score = score

        extra_queries = [
            "site:gov.au",
            "site:qld.gov.au",
            "site:vic.gov.au",
            "site:nsw.gov.au",
            "site:tas.gov.au",
            "site:sa.gov.au",
            "site:wa.gov.au",
        ]
        extra_queries.extend(self._australia_domain_hints(company_name))

        for variant in self._company_keywords(company_name):
            enriched = self._enrich_via_public_search(
                company_name=variant,
                country=country,
                extra_queries=extra_queries,
            )
            if not enriched:
                continue
            score = self._contact_score(enriched)
            if score > best_score:
                best_match = enriched
                best_score = score
        return best_match

    def _enrich_via_public_search(
        self,
        *,
        company_name: str,
        country: str,
        extra_queries: list[str] | None = None,
    ) -> EnrichedContact | None:
        best_match: EnrichedContact | None = None
        best_score = -1
        queries = [
            f'"{company_name}" {country} contact',
            f"{company_name} {country} contact",
            f"{company_name} {country} company website",
        ]
        for prefix in extra_queries or []:
            queries.insert(0, f'{prefix} "{company_name}" {country}')
        for query in queries:
            for result in self._search(query):
                enriched = self._extract_from_page(result["url"], country=country)
                if not enriched:
                    continue
                score = self._contact_score(enriched)
                if score > best_score:
                    best_match = enriched
                    best_score = score
        return best_match

    def _lookup_vietnam_yellowpages(self, keyword: str) -> str | None:
        response = self._request(
            self.yellowpages_search_endpoint,
            params={"keyword": keyword, "where": "", "timcongty": "ON"},
        )
        if not response:
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.select("a[href]"):
            href = anchor.get("href", "").strip()
            if "/listings/" not in href:
                continue
            return self._normalize_result_url(href)
        return None

    def _lookup_germany_gelbeseiten(self, keyword: str) -> list[str]:
        response = self._request(
            self.gelbeseiten_search_endpoint,
            method="post",
            data={"WAS": keyword, "WO": "", "pid": ""},
        )
        if not response:
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        results: list[str] = []
        seen: set[str] = set()
        for anchor in soup.select("a[href]"):
            href = anchor.get("href", "").strip()
            if "/gsbiz/" not in href:
                continue
            normalized = self._normalize_result_url(urljoin(str(response.url), href))
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            results.append(normalized)
            if len(results) >= 5:
                break
        return results

    def _search(self, query: str) -> list[dict[str, str]]:
        results = self._search_duckduckgo(query)
        if results:
            return results
        return self._search_bing(query)

    def _search_duckduckgo(self, query: str) -> list[dict[str, str]]:
        response = self._request(
            self.search_endpoint,
            params={"q": query},
        )
        if not response:
            return []
        soup = BeautifulSoup(response.text, "html.parser")

        results: list[dict[str, str | int]] = []
        for index, anchor in enumerate(soup.select("a.result__a")[:8]):
            raw_url = anchor.get("href", "").strip()
            title = anchor.get_text(" ", strip=True)
            normalized_url = self._normalize_result_url(raw_url)
            if not normalized_url:
                continue
            domain = self._normalized_domain(normalized_url)
            if domain in self.ignored_domains:
                continue
            score = self._result_score(url=normalized_url, title=title, index=index)
            results.append({"url": normalized_url, "title": title, "score": score})

        results.sort(key=lambda item: int(item["score"]), reverse=True)
        return [{"url": str(item["url"]), "title": str(item["title"])} for item in results]

    def _search_bing(self, query: str) -> list[dict[str, str]]:
        response = self._request(
            self.bing_search_endpoint,
            params={"q": query},
        )
        if not response:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        results: list[dict[str, str | int]] = []
        for index, item in enumerate(soup.select("li.b_algo")[:8]):
            anchor = item.select_one("h2 a[href]")
            if not anchor:
                continue
            raw_url = anchor.get("href", "").strip()
            title = anchor.get_text(" ", strip=True)
            normalized_url = self._normalize_result_url(raw_url)
            if not normalized_url:
                continue
            domain = self._normalized_domain(normalized_url)
            if domain in self.ignored_domains:
                continue
            score = self._result_score(url=normalized_url, title=title, index=index)
            results.append({"url": normalized_url, "title": title, "score": score})

        results.sort(key=lambda item: int(item["score"]), reverse=True)
        return [{"url": str(item["url"]), "title": str(item["title"])} for item in results]

    def _extract_from_page(
        self,
        url: str,
        *,
        country: str,
        follow_company_website: bool = True,
    ) -> EnrichedContact | None:
        response = self._request(url)
        if not response or response.status_code >= 400:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        page_url = str(response.url)
        page_domain = self._normalized_domain(page_url)
        email, phone = self._extract_direct_contacts(soup=soup, page_domain=page_domain, country=country)
        website_url = self._extract_company_website(
            soup=soup,
            page_url=page_url,
            page_domain=page_domain,
        )

        if follow_company_website and page_domain in self.directory_domains and website_url:
            website_match = self._extract_from_company_website(website_url, country=country)
            if website_match:
                email = website_match.email or email
                phone = website_match.phone or phone
                website_url = website_match.website or website_url
                contact_source_url = website_match.contact_source_url
            else:
                contact_source_url = page_url
        else:
            contact_source_url = page_url

        if not email and not phone:
            return None

        return EnrichedContact(
            website=self._website_from_url(website_url or page_url),
            contact_source_url=contact_source_url,
            email=email,
            phone=phone,
        )

    def _extract_from_company_website(self, website_url: str, *, country: str) -> EnrichedContact | None:
        response = self._request(website_url)
        if not response or response.status_code >= 400:
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        page_url = str(response.url)
        page_domain = self._normalized_domain(page_url)
        email, phone = self._extract_direct_contacts(soup=soup, page_domain=page_domain, country=country)

        contact_urls = self._contact_page_candidates(soup=soup, base_url=page_url)
        for contact_url in contact_urls[:4]:
            contact_response = self._request(contact_url)
            if not contact_response or contact_response.status_code >= 400:
                continue
            contact_soup = BeautifulSoup(contact_response.text, "html.parser")
            candidate_email, candidate_phone = self._extract_direct_contacts(
                soup=contact_soup,
                page_domain=self._normalized_domain(str(contact_response.url)),
                country=country,
            )
            email = email or candidate_email
            phone = phone or candidate_phone
            if email and phone:
                return EnrichedContact(
                    website=self._website_from_url(page_url),
                    contact_source_url=str(contact_response.url),
                    email=email,
                    phone=phone,
                )

        if not email and not phone:
            return None
        return EnrichedContact(
            website=self._website_from_url(page_url),
            contact_source_url=page_url,
            email=email,
            phone=phone,
        )

    def _extract_direct_contacts(
        self,
        *,
        soup: BeautifulSoup,
        page_domain: str,
        country: str,
    ) -> tuple[str | None, str | None]:
        text = soup.get_text("\n", strip=True)
        emails = [
            email
            for email in sorted(set(self.email_pattern.findall(text)))
            if "@" in email and "example." not in email.lower()
        ]
        phones = [
            phone
            for phone in sorted(set(self.phone_pattern.findall(text)))
            if len(re.sub(r"\D", "", phone)) >= 8
        ]
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if href.startswith("mailto:"):
                email = self._normalize_mailto_email(href)
                if email:
                    emails.append(email)
            elif href.startswith("tel:"):
                phones.append(href.removeprefix("tel:"))
        email = self._pick_best_email(sorted(set(emails)), page_domain=page_domain)
        phone = self._pick_best_phone(sorted(set(phones)), country=country)
        return email, phone

    def _extract_company_website(
        self,
        *,
        soup: BeautifulSoup,
        page_url: str,
        page_domain: str,
    ) -> str | None:
        if page_domain not in self.directory_domains:
            return page_url

        candidates: list[tuple[int, str]] = []
        for anchor in soup.select("a[href]"):
            href = self._normalize_result_url(urljoin(page_url, anchor.get("href", "").strip()))
            if not href:
                continue
            domain = self._normalized_domain(href)
            if not domain or domain == page_domain or domain in self.directory_domains:
                continue
            if domain in self.social_domains or domain in self.ignored_domains:
                continue
            text = anchor.get_text(" ", strip=True).lower()
            score = 0
            if "website" in text or "webseite" in text:
                score += 20
            if any(keyword in href.lower() for keyword in self.contact_keywords):
                score += 5
            score += 10
            candidates.append((score, href))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def _contact_page_candidates(self, *, soup: BeautifulSoup, base_url: str) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()

        for anchor in soup.select("a[href]"):
            href = anchor.get("href", "").strip()
            if not href or href.startswith(("mailto:", "tel:", "javascript:")):
                continue
            absolute = self._normalize_result_url(urljoin(base_url, href))
            if not absolute or absolute in seen:
                continue
            lowered = absolute.lower()
            text = anchor.get_text(" ", strip=True).lower()
            if any(keyword in lowered or keyword in text for keyword in self.contact_keywords):
                seen.add(absolute)
                candidates.append(absolute)

        standard_paths = [
            "/contact",
            "/contact-us",
            "/kontakt",
            "/impressum",
            "/en/contact",
            "/lien-he",
        ]
        parsed = urlparse(base_url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        for path in standard_paths:
            absolute = self._normalize_result_url(urljoin(root, path))
            if absolute and absolute not in seen:
                seen.add(absolute)
                candidates.append(absolute)

        return candidates

    def _request(
        self,
        url: str,
        *,
        method: str = "get",
        params: dict | None = None,
        data: dict | None = None,
    ) -> requests.Response | None:
        request_method = requests.post if method.lower() == "post" else requests.get
        kwargs = {
            "timeout": self.timeout_seconds,
            "headers": {"User-Agent": self.user_agent},
            "allow_redirects": True,
        }
        if params:
            kwargs["params"] = params
        if data:
            kwargs["data"] = data
        try:
            response = request_method(url, **kwargs)
            response.raise_for_status()
            return response
        except SSLError:
            try:
                kwargs["verify"] = False
                response = request_method(url, **kwargs)
                response.raise_for_status()
                return response
            except RequestException:
                return None
        except RequestException:
            return None

    def _result_score(self, *, url: str, title: str, index: int) -> int:
        score = max(0, 10 - index)
        lowered = f"{url} {title}".lower()
        domain = self._normalized_domain(url)
        if any(keyword in lowered for keyword in self.contact_keywords):
            score += 20
        if domain in self.directory_domains:
            score += 10
        else:
            score += 15
        return score

    def _company_keywords(self, company_name: str) -> list[str]:
        variants = [company_name.strip()]
        for separator in [" - ", " – ", " | ", "/"]:
            if separator in company_name:
                primary = company_name.split(separator, 1)[0].strip()
                if primary and primary not in variants:
                    variants.append(primary)
        cleaned = re.sub(r"[.,()]+", " ", company_name)
        cleaned = re.sub(
            r"\b(co|co ltd|company limited|limited|corp|corporation|joint stock company|jsc|gmbh|kg|llc|fzc|fze)\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned and cleaned not in variants:
            variants.append(cleaned)
        council_variant = re.sub(r"\bregional council\b", "council", cleaned, flags=re.IGNORECASE).strip()
        if council_variant and council_variant not in variants and council_variant != cleaned:
            variants.append(council_variant)
        shire_variant = re.sub(r"\bshire council\b", "council", cleaned, flags=re.IGNORECASE).strip()
        if shire_variant and shire_variant not in variants and shire_variant != cleaned:
            variants.append(shire_variant)
        return variants

    def _australia_domain_hints(self, company_name: str) -> list[str]:
        lowered = company_name.strip().lower()
        hints: list[str] = []
        if "transport and main roads" in lowered or "roadtek" in lowered:
            hints.extend(["site:tmr.qld.gov.au", "site:qld.gov.au/transport"])
        if "queensland rail" in lowered:
            hints.extend(["site:queenslandrail.com.au", "site:qr.com.au"])
        if "townsville" in lowered and "port" in lowered:
            hints.append("site:townsville-port.com.au")
        if "council" in lowered:
            hints.extend(
                [
                    "site:qld.gov.au",
                    "site:vic.gov.au",
                    "site:nsw.gov.au",
                    "site:tas.gov.au",
                ]
            )
        deduped: list[str] = []
        for hint in hints:
            if hint not in deduped:
                deduped.append(hint)
        return deduped

    def _lookup_australia_contact_hints(self, company_name: str) -> list[str]:
        lowered = company_name.strip().lower()
        candidates: list[str] = []
        if "transport and main roads" in lowered or "roadtek" in lowered:
            candidates.append("https://www.qld.gov.au/transport/contacts/roads?content=tmr-contact-us")
        if "charters towers regional council" in lowered:
            candidates.extend(
                [
                    "https://www.charterstowers.qld.gov.au/Contact/Contact-us",
                    "https://www.charterstowers.qld.gov.au/Contact",
                ]
            )
        if "queensland rail" in lowered:
            candidates.append("https://www.queenslandrail.com.au/aboutus/contact")
        if "port of townsville" in lowered:
            candidates.append("https://www.townsville-port.com.au/contact/")
        if "mount alexander shire council" in lowered:
            candidates.extend(
                [
                    "https://www.mountalexander.vic.gov.au/Council/Contact-us/Email-us",
                    "https://www.mountalexander.vic.gov.au/Council/Contact-us/Call-us",
                ]
            )
        deduped: list[str] = []
        for url in candidates:
            if url not in deduped:
                deduped.append(url)
        return deduped

    def _contact_score(self, enriched: EnrichedContact) -> int:
        score = 0
        if enriched.email:
            score += 30
        if enriched.phone:
            score += 20
        if enriched.email and enriched.phone:
            score += 10
        lowered = enriched.contact_source_url.lower()
        if any(keyword in lowered for keyword in self.contact_keywords):
            score += 10
        if self._normalized_domain(enriched.contact_source_url) in self.directory_domains:
            score += 5
        return score

    def _pick_best_email(self, emails: list[str], *, page_domain: str) -> str | None:
        cleaned = [email.strip() for email in emails if email.strip()]
        page_token = page_domain.split(".")[0] if page_domain else ""
        if page_domain and page_domain not in self.directory_domains:
            matching_domain = [
                email
                for email in cleaned
                if page_token and page_token in email.split("@")[-1].lower()
            ]
            if matching_domain:
                return matching_domain[0]
        preferred = [
            email
            for email in cleaned
            if not any(marker in email.lower() for marker in self.noisy_email_markers)
        ]
        candidates = preferred or cleaned
        return candidates[0] if candidates else None

    def _pick_best_phone(self, phones: list[str], *, country: str) -> str | None:
        cleaned = [re.sub(r"\s+", " ", phone).strip() for phone in phones if phone.strip()]
        preferred_prefix = self.country_dialing_codes.get(country.strip().lower())
        if preferred_prefix:
            preferred = [
                phone
                for phone in cleaned
                if re.sub(r"\s+", "", phone).startswith(preferred_prefix.replace(" ", ""))
            ]
            if preferred:
                return preferred[0]
        return cleaned[0] if cleaned else None

    @staticmethod
    def _normalize_result_url(url: str) -> str:
        if not url:
            return ""
        if url.startswith("//"):
            url = f"https:{url}"
        parsed = urlparse(url)
        if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
            query = parse_qs(parsed.query)
            uddg = query.get("uddg")
            if uddg:
                return requote_uri(unquote(uddg[0]))
        return requote_uri(url)

    @staticmethod
    def _normalized_domain(url: str) -> str:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host

    @staticmethod
    def _website_from_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _normalize_mailto_email(href: str) -> str:
        raw = href.removeprefix("mailto:")
        if not raw:
            return ""
        parsed = urlparse(raw)
        candidate = parsed.path or raw.split("?", 1)[0]
        candidate = unquote(candidate).strip()
        return candidate if "@" in candidate else ""
