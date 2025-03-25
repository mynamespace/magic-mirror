#!/usr/bin/env python3
import os
import subprocess
import urllib.parse
import configparser
import re
from helpers import normalize_html, check_attrs, php_rename, fix_query_strings, pretty_print
from php_refactor import extract_php_includes
from prompt_toolkit.shortcuts import input_dialog
from prompt_toolkit.shortcuts import checkboxlist_dialog


def main():
    # Read configuration from config.ini
    config = configparser.ConfigParser()
    config.read('config.ini')
    mirror_path = config.get('DEFAULT', 'mirror_path', fallback='.')

    domains = []
    domains_config = config.get('domains', 'domains_to_mirror', fallback='')
    
    available_domains = []
    if domains_config:
        available_domains = domains_config.split(',')
    
    if available_domains:
        domains = checkboxlist_dialog(
            title="Domain",
            ok_text="Proceed",
            cancel_text="Cancel",
            text="Choose one or more domains",
                values=[(d, d) for d in available_domains]).run()

    if not domains or len(domains) == 0:
        domains = []
        domain = input_dialog(
            title='Domain',
            ok_text="Proceed",
            cancel_text="Cancel",
            text="Enter the complete website address (e.g. www.example.org)").run()
        if domain:
            domains.append(domain)

    if not domains or len(domains) == 0:
        return

    options = checkboxlist_dialog(
        title="Operations to execute",
        ok_text="Proceed",
        cancel_text="Cancel",
        text=f"What do you want to do with {', '.join(domains)}?",
        values=[
            ("mirror", "Create a mirror"),
            ("check-attrs", "Look for additional resources in attributes"),
            ("fix-query", "Fix filenames with query strings"),
            ("normalize-html", "Fix code and rename files to .html"),
            ("php-rename", "Rename .html files to .php"),
            ("pretty-print", "Format HTML/PHP/ASP code with indentation"),
            ("php-includes", "Extract common blocks into PHP include files")
        ]
    ).run()

    if not options or len(options) == 0:
        return

    option_check_attrs = False
    attrs = "data-lazyload,data-bkg,data-src,data-image-src"
    if options and 'check-attrs' in options:
        option_check_attrs = True
        attrs = input_dialog(
            title='Domain',
            text="List additional attributes to search for resources, separated by commas. (e.g. data-src,data-attr)",
            default=attrs).run()
    
    # PHP includes options
    php_includes_options = {}
    if options and 'php-includes' in options:
        if config.has_section('PHP_Includes'):
            php_includes_options = {
                'min_block_size': config.getint('PHP_Includes', 'min_block_size', fallback=50),
                'similarity_threshold': config.getfloat('PHP_Includes', 'similarity_threshold', fallback=0.9),
                'min_occurrences': config.getint('PHP_Includes', 'min_occurrences', fallback=2)
            }
        else:
            min_block_size = input_dialog(
                title='Minimum block size',
                text="Minimum size in characters to consider a block (default: 50)",
                default="50").run()
            php_includes_options['min_block_size'] = int(min_block_size) if min_block_size else 50
            
            similarity_threshold = input_dialog(
                title='Similarity threshold',
                text="Threshold for considering blocks similar (0.0-1.0). A value of 1.0 means identical, 0.9 means 90% similar (default: 0.9)",
                default="0.9").run()
            php_includes_options['similarity_threshold'] = float(similarity_threshold) if similarity_threshold else 0.9
            
            min_occurrences = input_dialog(
                title='Minimum occurrences',
                text="Minimum number of occurrences to extract a block (default: 2)",
                default="2").run()
            php_includes_options['min_occurrences'] = int(min_occurrences) if min_occurrences else 2

    for domain in domains:

        # Add https:// if the scheme is not present
        if not urllib.parse.urlparse(domain).scheme:
            domain = "https://" + domain
            base_url = domain

            download_dir = domain.replace("https://", "")

            # Use the mirror_path from config
            download_path = os.path.join(mirror_path, download_dir)

            if 'mirror' in options:
                # 1. Initial execution of wget for site mirroring
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

                print(f"URLs found: {extra_urls}...")

                # Separate URLs into page files and static resources
                page_urls = set()
                static_urls = set()
                
                for url in extra_urls:
                    # Check if the URL points to a page file (HTML, ASP, PHP, etc.)
                    if re.search(r'\.(html|htm|asp|php|jsp|aspx|do|cgi)(\?|$)', url, flags=re.IGNORECASE):
                        page_urls.add(url)
                    else:
                        static_urls.add(url)
                
                # Download static resources with basic wget
                for url in static_urls:
                    subprocess.run(["wget", "-x", "-P", mirror_path, url])
                
                # Download page files with more options similar to mirror mode
                for url in page_urls:
                    wget_cmd = [
                        "wget",
                        "--convert-links",
                        "--adjust-extension",
                        "--page-requisites",
                        "--no-parent",
                        "--restrict-file-names=ascii,windows",
                        "-x",  # Keep directory structure
                        "-P", mirror_path,
                        url
                    ]
                    subprocess.run(wget_cmd)
            
            # Apply user options to all files, including both original and newly downloaded ones
            if 'fix-query' in options:
                fix_query_strings(domain, download_path)
                
            if "normalize-html" in options:
                normalize_html(domain, download_path)

            if "php-rename" in options:
                php_rename(domain, download_path)
                
            if "pretty-print" in options:
                pretty_print(domain, download_path)
            
            if "php-includes" in options:
                extract_php_includes(
                    domain, 
                    os.path.join(mirror_path, download_dir),
                    min_block_size=php_includes_options.get('min_block_size', 50),
                    similarity_threshold=php_includes_options.get('similarity_threshold', 0.9),
                    min_occurrences=php_includes_options.get('min_occurrences', 2),
                    debug=True  # Enable debug mode
                )
                if "pretty-print" in options:
                    pretty_print(domain, download_path)


if __name__ == '__main__':
    main()
