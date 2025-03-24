#!/usr/bin/env python3
import os
import subprocess
import urllib.parse
import re
import configparser
from bs4 import BeautifulSoup
from helpers import is_probably_url, normalize_html, check_attrs, php_rename, fix_query_strings, pretty_print
from prompt_toolkit.shortcuts import input_dialog
from prompt_toolkit.shortcuts import checkboxlist_dialog


def main():
    # Read configuration from config.ini
    config = configparser.ConfigParser()
    config.read('config.ini')
    mirror_path = config.get('DEFAULT', 'mirror_path', fallback='.')

    domains = []
    if os.path.exists("domains.txt"):
        available_domains = []
        with open('domains.txt', 'r') as file:
            for line in file:
                available_domains.append(line.strip())
            if available_domains:
                domains = checkboxlist_dialog(
                    title="Dominio",
                    ok_text="Procedi",
                    cancel_text="Annulla",
                    text="Scegli uno o più domini",
                values=[(d, d) for d in available_domains]).run()

    if not domains or len(domains) == 0:
        domain = input_dialog(
            title='Dominio',
            ok_text="Procedi",
            cancel_text="Annulla",
            text="Inserisci l'indirizzo completo del sito (es. www.example.org)").run()
        if domain:
            domains.append(domain)

    if not domains or len(domains) == 0:
        return

    options = checkboxlist_dialog(
        title="Operazioni da eseguire",
        ok_text="Procedi",
        cancel_text="Annulla",
        text=f"Cosa vuoi fare con {', '.join(domains)}?",
        values=[
            ("mirror", "Esegui il mirror"),
            ("check-attrs", "Cerca risorse aggiuntive negli attributi"),
            ("fix-query", "Correggi i nomi dei file con query string"),
            ("normalize-html", "Correggi codice e rinomina i file in .html"),
            ("php-rename", "Rinomina i file .html in .php"),
            ("pretty-print", "Formatta il codice HTML/PHP/ASP con indentazione")
        ]
    ).run()

    if not options or len(options) == 0:
        return

    option_check_attrs = False
    attrs = "data-lazyload,data-bkg,data-src,data-image-src"
    if options and 'check-attrs' in options:
        option_check_attrs = True
        attrs = input_dialog(
            title='Dominio',
            text="Elenca gli attributi aggiuntivi in cui cercare risorse, separati da virgole. (es data-src,data-attr)",
            default=attrs).run()

    for domain in domains:

        # Aggiunge https:// se lo schema non è presente
        if not urllib.parse.urlparse(domain).scheme:
            domain = "https://" + domain
            base_url = domain

            download_dir = domain.replace("https://", "")

            # Use the mirror_path from config
            download_path = os.path.join(mirror_path, download_dir)

            if 'mirror' in options:
                # 1. Esecuzione iniziale di wget per mirroring del sito
                wget_cmd = [
                    "wget",
                    "--mirror",
                    "--convert-links",
                    "--adjust-extension",
                    "--page-requisites",
                    "--no-parent",
                    "--restrict-file-names=ascii,windows",
                    "-P", mirror_path,  # Set the download directory to download_path
                    base_url
                ]
                subprocess.run(wget_cmd)

            if option_check_attrs:
                extra_urls = check_attrs(domain, download_path, attrs)

                print(f"Url trovati: {extra_urls}...")

                # 3. Scarica le risorse aggiuntive mantenendo la struttura delle directory (-x)
                for url in extra_urls:
                    subprocess.run(["wget", "-x", "-P", mirror_path, url])

            # Step 4: Se attivato, corregge i nomi dei file con query string
            if 'fix-query' in options:
                fix_query_strings(domain, download_path)
                
            if "normalize-html" in options:
                normalize_html(domain, download_path)

            if "php-rename" in options:
                php_rename(domain, download_path)

            if "pretty-print" in options:
                pretty_print(domain, download_path)


if __name__ == '__main__':
    main()
