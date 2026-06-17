# DataPrep Tool

DataPrep Tool is a privacy-focused web application that removes personally identifiable information (PII) from text and files before they are used with AI tools, shared externally, or stored. It was built as a learning project and a real commercial product, combining hands-on backend development with practical security, deployment, and DevOps experience.

The core idea is simple: people increasingly paste resumes, client data, and internal documents into AI tools like ChatGPT. Doing so often exposes personal information that should never leave the original document. DataPrep Tool automatically detects and masks this sensitive information, so the underlying content can still be used safely.

**Live demo:** https://dataprep.sofiialutsenko.com

---

## What It Does

The tool currently detects and masks the following categories of personal information:

- Email addresses, including obfuscated formats such as "user [at] domain.com" or "user(at)domain[dot]com"
- Phone numbers in a wide range of international formats, including country codes, area codes in parentheses, various separators (spaces, dashes, dots, slashes), and extensions
- Person names, detected using natural language processing rather than simple pattern matching, so that real names are masked while technical terms like "Python" or "React" are not mistakenly flagged

Users can either paste raw text or upload a `.txt` or `.csv` file. The tool processes the content, replaces sensitive information with clear placeholders such as `[EMAIL]`, `[PHONE]`, and `[NAME]`, and returns a cleaned version of the file or text. For CSV files, the tool also protects against CSV injection attacks, ensuring that formulas hidden in spreadsheet cells cannot execute when the file is later opened in Excel or Google Sheets.

The interface is intentionally minimal: a drag-and-drop upload area, a clear status indicator, a log of what was cleaned, and a short explanation of what categories of data are removed. Before processing any file, users must acknowledge a disclaimer stating that the tool may not catch all personal information and that they remain responsible for reviewing the output.

---

## Why This Project Exists

This project was built with two goals in mind. The first was to gain real, practical experience as a backend developer by building something end-to-end rather than following tutorials. The second was to create a small, genuinely useful product that could eventually generate income, particularly for freelancers, students, small HR teams, and other individuals who cannot justify paying for expensive enterprise-grade data anonymization tools.

Existing solutions for PII masking are largely aimed at large companies with compliance departments and enterprise budgets. DataPrep Tool intentionally targets the gap below that: people who need a simple, affordable, easy-to-use tool without complex setup or long-term contracts.

---

## How It Works Technically

The backend is built with Python and FastAPI. Incoming text or files are validated, then passed through a masking pipeline. Email and phone number detection rely on carefully constructed regular expressions designed to handle a wide variety of real-world formatting, including international standards, obfuscated text, and common human typing patterns. Name detection uses spaCy, a natural language processing library, to identify person names based on context rather than rigid patterns. A whitelist mechanism prevents common technology terms from being misidentified as names.

For file uploads, the backend reads files in chunks rather than loading them entirely into memory at once, which protects against memory exhaustion attacks. CSV files are parsed using Python's standard CSV module rather than naive string splitting, ensuring that quoted fields containing commas are handled correctly. Any field that begins with a character commonly used to trigger spreadsheet formulas is automatically escaped.

The API includes rate limiting to prevent abuse, since the file-processing endpoint is currently public and does not require authentication. Where appropriate, computationally heavy operations are run in a background thread pool so that a single large file does not block the server from responding to other users.

The frontend is built with plain HTML, CSS, and JavaScript, without any frontend framework. This was a deliberate choice for the first version, prioritizing speed of development and a clear understanding of every line of code. The interface uses the Fetch API to communicate with the backend, handles drag-and-drop file uploads natively, and provides real-time feedback during processing.

---

## Testing and Code Quality

The project includes an extensive automated test suite covering both the core masking logic and the API endpoints. Tests verify correct behavior for standard cases, such as properly formatted emails and phone numbers, as well as edge cases such as obfuscated email addresses, international phone number formats, names written with or without a surname, and known limitations such as dates that may be mistaken for phone numbers or numeric identifiers like IBANs that cannot be reliably distinguished from phone numbers using pattern matching alone.

Throughout development, particular attention was paid to security. The codebase has gone through multiple rounds of review focused on identifying vulnerabilities such as regular expression denial of service (ReDoS), memory exhaustion from unbounded file reads, HTTP header injection through unsanitized filenames, and event loop blocking caused by running CPU-intensive operations inside asynchronous functions without offloading them to a thread pool.

---

## Infrastructure and Deployment

The backend runs inside a Docker container on a virtual private server hosted by Hetzner, running Ubuntu 24.04. Nginx is configured as a reverse proproxy in front of the application, handling HTTPS termination using a free SSL certificate issued and automatically renewed through Let's Encrypt. The server is secured using SSH key-based authentication only, with root login disabled and a dedicated non-root user configured for all administrative tasks. A firewall restricts access to only the necessary ports.

The frontend is hosted separately on Netlify as a static site. Both the frontend and backend are served under custom subdomains of a personal domain, with DNS managed through Namecheap.

This project was initially deployed using Railway for convenience during early development, then migrated to a self-managed VPS to reduce ongoing hosting costs and to gain hands-on experience with server administration, containerization, and production deployment practices.

---

## Current Limitations

This is an evolving project, and several limitations are intentionally documented rather than hidden. The tool does not yet detect physical addresses, dates of birth, organization names, or government identification numbers. Phone number detection, due to the nature of pattern matching, can occasionally produce false positives on other numeric sequences such as dates or international bank account numbers. Email addresses using non-Latin characters or unusual formats such as IP-address-based domains are not currently supported. File size is currently limited to keep processing fast and predictable, and only plain text and CSV files are supported, with support for additional formats such as Word documents planned for a future version.

These limitations are communicated to users directly within the interface, and a disclaimer checkbox ensures users acknowledge that automated detection is not infallible before processing any file.

---

## Roadmap

Planned future improvements include expanding the categories of personal information that can be detected, such as organization names, physical addresses, and dates of birth, using the same natural language processing approach already in place for personal names. Further along, the project plans to introduce user accounts, allowing for saved preferences, usage history, and a foundation for a subscription-based pricing model. Additional planned features include support for exporting cleaned files in formats such as PDF or Word, batch processing of multiple files at once, and a visual redesign of the frontend using React, incorporating custom 2D animations.

---

## Technology Summary

The backend is written in Python using FastAPI, with Pydantic for data validation and pydantic-settings for configuration management. Person name detection uses spaCy's natural language processing model. The application is tested using pytest and served using Uvicorn. Rate limiting is handled with SlowAPI, and asynchronous task offloading uses AnyIO. The frontend is built with plain HTML, CSS, and JavaScript. Deployment relies on Docker, Nginx, and Let's Encrypt for SSL, running on a Hetzner virtual private server, with the frontend hosted separately on Netlify. Version control is managed through Git and GitHub.

---

## About This Project

This project is being developed and maintained by a self-taught backend developer currently based in Germany, with the long-term goal of working professionally as a backend engineer. It reflects an ongoing commitment to learning through building real, functioning software rather than isolated exercises, with careful attention paid to security, code quality, and production-readiness at every stage.
