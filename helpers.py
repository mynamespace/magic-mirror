import urllib.parse
import re
import os
from bs4 import BeautifulSoup


def is_probably_url(value: str) -> bool:
    """
    Determina se una stringa sembra rappresentare un URL.
    Restituisce True se:
      - non contiene spazi e
      - inizia con "http://", "https://", "/", "./", "../"
        oppure contiene una barra "/" oppure termina con .html (inclusi .asp.html/.php.html).
    Altrimenti restituisce False.
    """
    if not value or ' ' in value:
        return False
    parsed = urllib.parse.urlparse(value)
    # Se è un URL assoluto (ha uno schema) ritorna True.
    if parsed.scheme:
        return True
    if value.startswith(("//", "http://", "https://", "/", "./", "../")):
        return True
    if "/" in value:
        return True
    if re.search(r'\.(asp|php)\.html$', value, flags=re.IGNORECASE) or re.search(r'\.html$', value, flags=re.IGNORECASE):
        return True
    return False

def check_attrs(domain: str, download_dir: str, attrs: str) -> set:
    """
    Checks for URLs in specified attributes of HTML files and adds them to the list of extra URLs.
    Also transforms absolute URLs that include the current domain into site-relative URLs.

    Args:
        domain (str): The website domain (e.g., 'https://example.com')
        download_dir (str): Directory containing the downloaded website files
        attrs (str): Comma-separated list of HTML attributes to check for URLs

    Returns:
        set: Set of additional URLs found in the specified attributes
    """
    # Parse domain for comparison
    parsed_domain = urllib.parse.urlparse(domain)
    domain_base = f"{parsed_domain.scheme}://{parsed_domain.netloc}"
    
    attrs_to_search = attrs.split(",") if attrs else []
    extra_urls = set()
    
    print(f"Checking attributes {attrs_to_search} in {download_dir}...")
    
    for root, dirs, files in os.walk(download_dir):
        for file in files:
            if file.endswith((".html", ".php", ".asp")):
                file_path = os.path.join(root, file)
                modified = False
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    soup = BeautifulSoup(f, "html.parser")
                    for tag in soup.find_all():
                        for attr, value in tag.attrs.items():
                            if attr in attrs_to_search and isinstance(value, str):
                                print(f"Checking attribute {attr} in {file_path}, value: {value}...")
                                if is_probably_url(value):
                                    # Add to extra URLs for downloading
                                    absolute_url = urllib.parse.urljoin(domain, value)
                                    extra_urls.add(absolute_url)
                                    
                                    # Transform absolute URLs with current domain to site-relative
                                    if value.startswith(domain_base):
                                        # Extract the path part and make it site-relative
                                        parsed_url = urllib.parse.urlparse(value)
                                        site_relative_url = parsed_url.path
                                        if parsed_url.query:
                                            site_relative_url += "?" + parsed_url.query
                                        if parsed_url.fragment:
                                            site_relative_url += "#" + parsed_url.fragment
                                            
                                        # Update the attribute value
                                        tag[attr] = site_relative_url
                                        modified = True
                
                # Save the file only if modifications were made
                if modified:
                    with open(file_path, "w", encoding="utf-8", errors="ignore") as f:
                        f.write(str(soup))
    
    return extra_urls

def fix_query_strings(domain: str, download_dir: str):
    """
    Cleans up files with query strings in their names by removing the '@' and subsequent characters.
    For example, 'page@param=value.html' becomes 'page.html'. Also updates all references to these
    files in HTML and CSS files to maintain link integrity.

    If a "clean" version of a file already exists, the one with query strings is deleted instead
    of being renamed.

    Args:
        domain (str): The website domain (not used in current implementation)
        download_dir (str): Directory containing the downloaded website files
    """
    # fix_mapping: mappa (relativo vecchio nome con '@' -> nuovo nome "pulito")
    fix_mapping = {}
    for root, dirs, files in os.walk(download_dir):
        for file in files:
            if "@" in file:
                old_full_path = os.path.join(root, file)
                # Nuovo nome: prendi la parte prima della '@'
                new_file_name = file.split("@")[0]
                new_full_path = os.path.join(root, new_file_name)
                # Se esiste già il file "pulito", elimina quello con '@'
                if os.path.exists(new_full_path):
                    os.remove(old_full_path)
                else:
                    os.rename(old_full_path, new_full_path)
                # Salva solo il nome vecchio e nuovo (senza il percorso)
                fix_mapping[file] = new_file_name

    # Step 5: Correggi i riferimenti nei file HTML
    for root, dirs, files in os.walk(download_dir):
        for file in files:
            if file.endswith(".html") or file.endswith(".css"):
                file_path = os.path.join(root, file)
                print(f"Processing {file_path}...")
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                # Sostituisci ogni riferimento vecchio con quello nuovo
                for old_ref, new_ref in fix_mapping.items():
                    content = content.replace(old_ref, new_ref)
                with open(file_path, "w", encoding="utf-8", errors="ignore") as f:
                    f.write(content)

def normalize_html(domain: str, download_dir: str):
    """
    Normalizes HTML files in a downloaded website directory by:
    1. Renaming .asp.html and .php.html files to .html
    2. Fixing relative URLs in HTML attributes (href, src, data-lazyload, data-src)
    3. Converting relative paths (../, ./) to absolute paths based on the domain
    4. Preserving existing absolute URLs, anchors, and special URIs (javascript:, data:, mailto:)

    Args:
        domain (str): The original website domain (e.g., 'https://example.com')
        download_dir (str): Directory containing the downloaded website files
    """
    # Get the domain for absolute URL conversion
    parsed_domain = urllib.parse.urlparse(domain)
    domain_base = f"{parsed_domain.scheme}://{parsed_domain.netloc}"

    for root, dirs, files in os.walk(download_dir):
        for file in files:
            if file.endswith(('.asp.html', '.php.html')):
                old_path = os.path.join(root, file)
                new_name = re.sub(
                    r'\.(asp|php)\.html$', '.html', file, flags=re.IGNORECASE)
                new_path = os.path.join(root, new_name)
                os.rename(old_path, new_path)

                # Update references in all HTML files
                for html_root, _, html_files in os.walk(download_dir):
                    for html_file in html_files:
                        if html_file.endswith(('.html', '.htm', '.asp', '.php', '.asp.html', '.php.html')):
                            html_path = os.path.join(
                                html_root, html_file)
                            try:
                                with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()

                                soup = BeautifulSoup(
                                    content, 'html.parser')
                                modified = False

                                # Calculate the relative path from domain root for the current file
                                relative_dir = os.path.relpath(
                                    html_root, download_dir)
                                if relative_dir == '.':
                                    relative_dir = ''

                                for tag in soup.find_all(True):
                                    # Only process href and src attributes
                                    for attr_name in ['href', 'src', 'data-lazyload', 'data-src', 'data-image-src']:
                                        if not tag.has_attr(attr_name):
                                            continue

                                        value = tag[attr_name]
                                        if not isinstance(value, str):
                                            continue

                                        new_value = value

                                        # Skip URLs that are:
                                        # - Already absolute paths
                                        # - Absolute URLs (http://, https://, //)
                                        # - Anchors only (#)
                                        # - JavaScript or data URIs
                                        if (not value.startswith(('/', 'http://', 'https://', '//', '#', 'javascript:', 'data:', 'mailto:', 'tel:')) and
                                                value.strip() and not value.startswith('{')):

                                            # Handle ../ paths
                                            if value.startswith('../'):
                                                path_parts = relative_dir.split(
                                                    os.sep)
                                                up_count = value.count(
                                                    '../')
                                                if len(path_parts) >= up_count:
                                                    new_path = '/'.join(
                                                        path_parts[:-up_count])
                                                    if new_path:
                                                        new_value = '/' + new_path + \
                                                            '/' + \
                                                            value[3 *
                                                                    up_count:]
                                                    else:
                                                        new_value = '/' + \
                                                            value[3 *
                                                                    up_count:]
                                            # Handle ./ paths
                                            elif value.startswith('./'):
                                                if relative_dir:
                                                    new_value = '/' + \
                                                        relative_dir + \
                                                        '/' + \
                                                        value[2:]
                                                else:
                                                    new_value = '/' + \
                                                        value[2:]
                                            # Handle relative paths without ./ or ../
                                            else:
                                                if relative_dir:
                                                    new_value = '/' + relative_dir + '/' + value
                                                else:
                                                    new_value = '/' + value

                                            modified = True

                                        # Convert domain-based absolute URLs to path-based
                                        elif value.startswith(domain_base):
                                            new_value = value[len(
                                                domain_base):]
                                            if not new_value.startswith('/'):
                                                new_value = '/' + new_value
                                            modified = True

                                        # Update .asp.html and .php.html extensions
                                        updated_value = re.sub(
                                            r'\.(asp|php)\.html($|\?|#)', r'.html\2', new_value, flags=re.IGNORECASE)
                                        if updated_value != new_value:
                                            new_value = updated_value
                                            modified = True

                                        # Clean up double slashes in paths (but keep // in protocol)
                                        if '://' in new_value:
                                            protocol, path = new_value.split(
                                                '://', 1)
                                            path = re.sub(
                                                r'//+', '/', path)
                                            new_value = f"{protocol}://{path}"
                                        else:
                                            new_value = re.sub(
                                                r'//+', '/', new_value)

                                        if new_value != value:
                                            tag[attr_name] = new_value

                                if modified:
                                    html_content = str(soup)
                                    # List of void elements that should be self-closing
                                    void_elements = ['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 
                                                    'link', 'meta', 'param', 'source', 'track', 'wbr']
                                    
                                    # Remove incorrect closing tags
                                    for tag in void_elements:
                                        html_content = re.sub(f'</{tag}>', '', html_content)
                                    
                                    with open(html_path, 'w', encoding='utf-8') as f:
                                        f.write(html_content)
                            except Exception as e:
                                print(
                                    f"Error processing {html_path}: {str(e)}")
                                
                                
def php_rename(domain: str, download_dir: str):
    """
    Renames all .html files to .php and updates all references to these files across the site.
    This includes updating links and other attributes that reference .html files to point to
    the new .php files instead.

    Args:
        domain (str): The website domain (not used in current implementation)
        download_dir (str): Directory containing the downloaded website files
    """
    # First pass: collect all HTML files that will be renamed
    html_files = set()
    for root, dirs, files in os.walk(download_dir):
        for file in files:
            if file.endswith('.html'):
                html_files.add(file)

    # Second pass: update references in all HTML and PHP files
    for root, dirs, files in os.walk(download_dir):
        for file in files:
            if file.endswith(('.asp.html', '.html', '.php')):
                file_path = os.path.join(root, file)
                modified = False
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        soup = BeautifulSoup(f, 'html.parser')
                        
                    # Update href attributes in links
                    for tag in soup.find_all(['a', 'link', 'area', 'base']):
                        if tag.has_attr('href'):
                            href = tag['href']
                            if isinstance(href, str):
                                # Extract the filename from the href
                                parsed = urllib.parse.urlparse(href)
                                path = parsed.path
                                filename = os.path.basename(path)
                                
                                if filename in html_files:
                                    # Replace .html with .php in the href
                                    new_filename = filename[:-5] + '.php'
                                    new_href = href.replace(filename, new_filename)
                                    tag['href'] = new_href
                                    modified = True
                    
                    # Update other attributes that might contain file references
                    for tag in soup.find_all():
                        for attr in ['src', 'data-src', 'data-href']:
                            if tag.has_attr(attr):
                                value = tag[attr]
                                if isinstance(value, str):
                                    parsed = urllib.parse.urlparse(value)
                                    path = parsed.path
                                    filename = os.path.basename(path)
                                    
                                    if filename in html_files:
                                        new_filename = filename[:-5] + '.php'
                                        new_value = value.replace(filename, new_filename)
                                        tag[attr] = new_value
                                        modified = True
                    
                    # Save changes if any modifications were made
                    if modified:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(str(soup))
                
                except Exception as e:
                    print(f"Error processing {file_path}: {str(e)}")

    # Final pass: rename all HTML files to PHP
    for root, dirs, files in os.walk(download_dir):
        for file in files:
            if file.endswith('.html'):
                old_path = os.path.join(root, file)
                new_path = os.path.join(root, file[:-5] + '.php')
                os.rename(old_path, new_path)


def pretty_print(domain: str, download_dir: str):
    """
    Applies pretty printing to HTML, PHP, and ASP files in the downloaded directory.
    This reformats the HTML content to be more readable with proper indentation.
    
    Args:
        domain (str): The website domain (not used in current implementation)
        download_dir (str): Directory containing the downloaded website files
    """
    print(f"Applying pretty print to files in {download_dir}...")
    
    # Keep track of processed files
    processed_files = 0
    
    # Process all HTML, PHP, and ASP files
    for root, dirs, files in os.walk(download_dir):
        for file in files:
            if file.endswith(('.html', '.php', '.asp', '.asp.html', '.php.html')):
                file_path = os.path.join(root, file)
                try:
                    # Read the file content
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Parse with BeautifulSoup using lxml parser if available, otherwise html.parser
                    try:
                        soup = BeautifulSoup(content, 'lxml')
                    except:
                        soup = BeautifulSoup(content, 'html.parser')
                    
                    # Pretty print the content
                    pretty_content = soup.prettify()
                    
                    # Fix self-closing tags that BeautifulSoup might have incorrectly formatted
                    # List of void elements that should be self-closing
                    void_elements = ['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 
                                    'link', 'meta', 'param', 'source', 'track', 'wbr']
                    
                    # Remove incorrect closing tags
                    for tag in void_elements:
                        pretty_content = re.sub(f'</{tag}>', '', pretty_content)
                    
                    # Write back the formatted content
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(pretty_content)
                    
                    processed_files += 1
                    if processed_files % 50 == 0:
                        print(f"Processed {processed_files} files...")
                        
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
    
    print(f"Pretty print completed. Processed {processed_files} files.")