#!/usr/bin/env python3

import os
import re
import hashlib
import difflib
from collections import defaultdict
from bs4 import BeautifulSoup


class PHPRefactor:
    def __init__(self, directory, min_block_size=50, similarity_threshold=0.9, min_occurrences=2, debug=False):
        """
        Initialize the PHP refactoring tool.
        
        Args:
            directory (str): Directory containing PHP files to analyze
            min_block_size (int): Minimum size in characters for a block to be considered
            similarity_threshold (float): Threshold for considering blocks similar (0.0-1.0)
            min_occurrences (int): Minimum number of occurrences for a block to be extracted
            debug (bool): Enable detailed debugging output
        """
        self.directory = directory
        self.min_block_size = min_block_size
        self.similarity_threshold = similarity_threshold
        self.min_occurrences = min_occurrences
        self.debug = debug
        self.php_files = []
        self.file_contents = {}
        self.common_blocks = defaultdict(list)
        self.includes_dir = os.path.join(directory, 'includes')
        
    def scan_directory(self):
        """
        Scan the directory for PHP files and load their contents.
        """
        print(f"Scanning directory: {self.directory}")
        for root, _, files in os.walk(self.directory):
            for file in files:
                if file.endswith('.php'):
                    file_path = os.path.join(root, file)
                    self.php_files.append(file_path)
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        self.file_contents[file_path] = f.read()
        
        print(f"Found {len(self.php_files)} PHP files")
        return self.php_files
    
    def _extract_potential_blocks(self, content):
        """
        Extract potential blocks from a PHP file using BeautifulSoup.
        This extracts HTML blocks, script tags, and other common elements.
        
        Args:
            content (str): PHP file content
            
        Returns:
            list: List of potential blocks with their metadata
        """
        blocks = []
        
        # Try to parse the content with BeautifulSoup
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract script tags
            for script in soup.find_all('script'):
                if len(str(script)) >= self.min_block_size:
                    blocks.append({
                        'type': 'script',
                        'content': str(script),
                        'hash': hashlib.md5(str(script).encode()).hexdigest()
                    })
            
            # Extract navigation menus (common patterns)
            for nav in soup.find_all(['nav', 'div'], class_=re.compile(r'(nav|menu|header|footer)', re.I)):
                if len(str(nav)) >= self.min_block_size:
                    blocks.append({
                        'type': 'navigation',
                        'content': str(nav),
                        'hash': hashlib.md5(str(nav).encode()).hexdigest()
                    })
                    
            # Extract headers
            header = soup.find('header')
            if header and len(str(header)) >= self.min_block_size:
                blocks.append({
                    'type': 'header',
                    'content': str(header),
                    'hash': hashlib.md5(str(header).encode()).hexdigest()
                })
                
            # Extract footers
            footer = soup.find('footer')
            if footer and len(str(footer)) >= self.min_block_size:
                blocks.append({
                    'type': 'footer',
                    'content': str(footer),
                    'hash': hashlib.md5(str(footer).encode()).hexdigest()
                })
            
            # Extract head content - specifically targeting CSS and favicon links
            head = soup.find('head')
            if head:
                # Find all link tags in the head
                link_tags = head.find_all('link')
                
                # Look for CSS and favicon links specifically
                css_favicon_links = []
                for link in link_tags:
                    if 'rel' in link.attrs and link['rel'] == 'stylesheet' or \
                       'type' in link.attrs and link['type'] == 'image/x-icon' or \
                       'href' in link.attrs and ('.css' in link['href'] or 'favicon' in link['href']):
                        css_favicon_links.append(link)
                
                # If we have consecutive CSS/favicon links, group them
                if len(css_favicon_links) >= 2:
                    # Find consecutive sequences
                    i = 0
                    while i < len(css_favicon_links):
                        # Start a new group
                        group = [css_favicon_links[i]]
                        j = i + 1
                        
                        # Find consecutive siblings
                        while j < len(css_favicon_links):
                            # Check if they are adjacent in the original HTML
                            if are_adjacent_siblings(css_favicon_links[j-1], css_favicon_links[j]):
                                group.append(css_favicon_links[j])
                                j += 1
                            else:
                                break
                        
                        # If we have a group of 2 or more, add it
                        if len(group) >= 2:
                            group_content = ''.join(str(tag) for tag in group)
                            if len(group_content) >= self.min_block_size:
                                blocks.append({
                                    'type': 'css_links',
                                    'content': group_content,
                                    'hash': hashlib.md5(group_content.encode()).hexdigest()
                                })
                        
                        i = j
                
                # Also look for meta tags groups
                meta_tags = head.find_all('meta')
                if len(meta_tags) >= 2:
                    i = 0
                    while i < len(meta_tags):
                        group = [meta_tags[i]]
                        j = i + 1
                        
                        while j < len(meta_tags):
                            if are_adjacent_siblings(meta_tags[j-1], meta_tags[j]):
                                group.append(meta_tags[j])
                                j += 1
                            else:
                                break
                        
                        if len(group) >= 2:
                            group_content = ''.join(str(tag) for tag in group)
                            if len(group_content) >= self.min_block_size:
                                blocks.append({
                                    'type': 'meta_tags',
                                    'content': group_content,
                                    'hash': hashlib.md5(group_content.encode()).hexdigest()
                                })
                        
                        i = j
            
            # Direct pattern matching for common blocks
            # This is a more targeted approach for specific patterns like CSS links
            raw_html = str(soup)
            
            # Pattern for CSS link tags (specifically looking for the pattern mentioned by the user)
            css_pattern = r'<link\s+href="/css/style\.css"[^>]*>\s*<link\s+href="/css/responsive\.css"[^>]*>\s*<link\s+href="/css/fotorama\.dev\.css"[^>]*>\s*<link\s+href="/images/favicon\.ico"[^>]*>'
            for match in re.finditer(css_pattern, raw_html, re.DOTALL):
                match_content = match.group(0)
                blocks.append({
                    'type': 'css_links',
                    'content': match_content,
                    'hash': hashlib.md5(match_content.encode()).hexdigest()
                })
            
            # More general pattern for consecutive link tags
            link_pattern = r'(<link[^>]+>\s*){3,}'  # 3 or more consecutive link tags
            for match in re.finditer(link_pattern, raw_html, re.DOTALL):
                match_content = match.group(0)
                if len(match_content) >= self.min_block_size:
                    blocks.append({
                        'type': 'link_group',
                        'content': match_content,
                        'hash': hashlib.md5(match_content.encode()).hexdigest()
                    })
                
        except Exception as e:
            print(f"Error parsing file with BeautifulSoup: {e}")
            
        # Also try regex-based extraction for PHP blocks
        php_blocks = re.findall(r'<\?php\s+(.+?)\s+\?>', content, re.DOTALL)
        for block in php_blocks:
            if len(block) >= self.min_block_size:
                blocks.append({
                    'type': 'php_code',
                    'content': f'<?php {block} ?>',
                    'hash': hashlib.md5(block.encode()).hexdigest()
                })
                
        return blocks
    
    def identify_common_blocks(self):
        """
        Identify common blocks across all PHP files.
        """
        print("Identifying common blocks...")
        all_blocks = []
        
        # Extract blocks from each file
        for file_path, content in self.file_contents.items():
            blocks = self._extract_potential_blocks(content)
            for block in blocks:
                block['file'] = file_path
                all_blocks.append(block)
        
        # Group similar blocks
        processed_hashes = set()
        for i, block1 in enumerate(all_blocks):
            if block1['hash'] in processed_hashes:
                continue
                
            similar_blocks = [block1]
            for block2 in all_blocks[i+1:]:
                # Skip if already processed or from the same file
                if block2['hash'] in processed_hashes or block1['file'] == block2['file']:
                    continue
                    
                # Check similarity using difflib
                similarity = difflib.SequenceMatcher(None, block1['content'], block2['content']).ratio()
                if similarity >= self.similarity_threshold:
                    similar_blocks.append(block2)
                    processed_hashes.add(block2['hash'])
            
            # If we found enough similar blocks, add to common_blocks
            if len(similar_blocks) >= self.min_occurrences:
                block_id = f"{block1['type']}_{len(self.common_blocks)}"
                self.common_blocks[block_id] = similar_blocks
                processed_hashes.add(block1['hash'])
        
        print(f"Found {len(self.common_blocks)} common blocks")
        return self.common_blocks
    
    def create_includes(self):
        """
        Create include files for common blocks.
        
        Returns:
            dict: Mapping of block_id to include file path
        """
        if not self.common_blocks:
            print("No common blocks found. Run identify_common_blocks() first.")
            return {}
            
        # Create includes directory if it doesn't exist
        if not os.path.exists(self.includes_dir):
            os.makedirs(self.includes_dir)
            
        include_files = {}
        
        for block_id, blocks in self.common_blocks.items():
            # Use the first block as the template
            content = blocks[0]['content']
            block_type = blocks[0]['type']
            
            # Create a filename for the include
            include_filename = f"{block_type}_{hashlib.md5(content.encode()).hexdigest()[:8]}.php"
            include_path = os.path.join(self.includes_dir, include_filename)
            
            # Write the include file
            with open(include_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            include_files[block_id] = include_path
            print(f"Created include file: {include_path}")
            
        return include_files
    
    def apply_includes(self, include_files):
        """
        Replace common blocks with include statements in the original files.
        
        Args:
            include_files (dict): Mapping of block_id to include file path
            
        Returns:
            int: Number of replacements made
        """
        replacements = 0
        
        # Debug information
        if self.debug:
            print("\n===== DEBUG: Found {} common blocks to replace =====".format(len(self.common_blocks)))
            for block_id, blocks in self.common_blocks.items():
                print("\nBlock ID: {}".format(block_id))
                print("Block type: {}, Occurrences: {}".format(blocks[0]['type'], len(blocks)))
                print("Sample content (first 100 chars): {}...".format(blocks[0]['content'][:100]))
                print("Files containing this block:")
                for i, block in enumerate(blocks):
                    print("  {}. {}".format(i+1, os.path.basename(block['file'])))
        
        for block_id, blocks in self.common_blocks.items():
            include_path = include_files[block_id]
            relative_include_path = os.path.relpath(include_path, self.directory)
            include_statement = f"<?php include '{relative_include_path}'; ?>\n"
            
            # Get the block type (first block in the list)
            block_type = blocks[0]['type']
            
            if self.debug:
                print("\n----- Processing block {} ({}) -----".format(block_id, block_type))
            
            # Process each file that contains this block
            for block in blocks:
                file_path = block['file']
                original_content = self.file_contents[file_path]
                
                if self.debug:
                    print("Attempting to replace in: {}".format(os.path.basename(file_path)))
                
                # Track if we've made a replacement for this block
                replacement_made = False
                
                # APPROACH 1: Direct string replacement (most reliable for exact matches)
                if block['content'] in original_content:
                    new_content = original_content.replace(block['content'], include_statement)
                    if new_content != original_content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        self.file_contents[file_path] = new_content
                        replacements += 1
                        replacement_made = True
                        print("Replaced block in {} (exact match)".format(os.path.basename(file_path)))
                elif self.debug:
                    print("  - Exact match failed")
                
                # APPROACH 2: HTML structure-based replacement for specific block types
                if not replacement_made and block_type in ['css_links', 'link_group', 'navigation', 'header', 'footer']:
                    if self.debug:
                        print("  - Trying structure-based replacement")
                    
                    # For CSS links and similar structured content
                    if block_type in ['css_links', 'link_group']:
                        # Extract all link tags from the block and create a fingerprint
                        link_tags = re.findall(r'<link[^>]+>', block['content'])
                        if link_tags:
                            # Create a pattern that matches these links with flexible whitespace
                            pattern = '\\s*'.join([re.escape(tag) for tag in link_tags])
                            matches = list(re.finditer(pattern, original_content, re.DOTALL))
                            
                            if matches:
                                # Replace the first match
                                match = matches[0]
                                new_content = original_content[:match.start()] + include_statement + original_content[match.end():]
                                with open(file_path, 'w', encoding='utf-8') as f:
                                    f.write(new_content)
                                self.file_contents[file_path] = new_content
                                replacements += 1
                                replacement_made = True
                                print("Replaced block in {} (link pattern match)".format(os.path.basename(file_path)))
                            elif self.debug:
                                print("  - Link pattern match failed. Found {} link tags".format(len(link_tags)))
                    
                    # For navigation, header, footer blocks
                    elif block_type in ['navigation', 'header', 'footer']:
                        # Extract key elements that uniquely identify this block
                        try:
                            soup = BeautifulSoup(block['content'], 'html.parser')
                            
                            # Find all links, classes, and IDs to create a fingerprint
                            links = [a.get('href', '') for a in soup.find_all('a')]
                            classes = [elem.get('class', []) for elem in soup.find_all(class_=True)]
                            ids = [elem.get('id', '') for elem in soup.find_all(id=True)]
                            
                            # Create a fingerprint from these elements
                            fingerprint = '|'.join(sorted(links + [c for cls in classes for c in cls] + ids))
                            
                            if self.debug:
                                print("  - Block fingerprint: {}...".format(fingerprint[:50]))
                            
                            # Now try to find a matching block in the file
                            file_soup = BeautifulSoup(original_content, 'html.parser')
                            potential_matches = file_soup.find_all(soup.name) if soup.name else []
                            
                            if self.debug:
                                print("  - Found {} potential matches with tag '{}'".format(len(potential_matches), soup.name))
                            
                            best_match = None
                            best_similarity = 0
                            
                            for potential_match in potential_matches:
                                # Create fingerprint for this potential match
                                p_links = [a.get('href', '') for a in potential_match.find_all('a')]
                                p_classes = [elem.get('class', []) for elem in potential_match.find_all(class_=True)]
                                p_ids = [elem.get('id', '') for elem in potential_match.find_all(id=True)]
                                p_fingerprint = '|'.join(sorted(p_links + [c for cls in p_classes for c in cls] + p_ids))
                                
                                # Calculate similarity
                                similarity = difflib.SequenceMatcher(None, fingerprint, p_fingerprint).ratio()
                                
                                if similarity > best_similarity:
                                    best_similarity = similarity
                                    best_match = potential_match
                            
                            if self.debug and best_match:
                                print("  - Best match similarity: {:.2f}".format(best_similarity))
                            
                            if best_match and best_similarity >= 0.8:  # High similarity threshold
                                # Found a match, replace it
                                match_str = str(best_match)
                                if match_str in original_content:
                                    new_content = original_content.replace(match_str, include_statement)
                                    with open(file_path, 'w', encoding='utf-8') as f:
                                        f.write(new_content)
                                    self.file_contents[file_path] = new_content
                                    replacements += 1
                                    replacement_made = True
                                    print("Replaced block in {} (structural match, similarity: {:.2f})".format(os.path.basename(file_path), best_similarity))
                        except Exception as e:
                            if self.debug:
                                print("  - Error in structural matching: {}".format(e))
                
                # APPROACH 3: DOM-based replacement for more complex structures
                if not replacement_made and block_type in ['script', 'meta_tags', 'php_code']:
                    if self.debug:
                        print("  - Trying DOM-based replacement")
                    
                    # For script tags
                    if block_type == 'script':
                        # Extract script content and attributes
                        try:
                            script_soup = BeautifulSoup(block['content'], 'html.parser')
                            script_tag = script_soup.find('script')
                            
                            if script_tag:
                                script_attrs = {k: v for k, v in script_tag.attrs.items()}
                                
                                # Find matching scripts in the file
                                file_soup = BeautifulSoup(original_content, 'html.parser')
                                for potential_script in file_soup.find_all('script'):
                                    # Check if attributes match
                                    attrs_match = True
                                    for k, v in script_attrs.items():
                                        if potential_script.get(k) != v:
                                            attrs_match = False
                                            break
                                    
                                    if attrs_match:
                                        # Found a match, replace it
                                        match_str = str(potential_script)
                                        if match_str in original_content:
                                            new_content = original_content.replace(match_str, include_statement)
                                            with open(file_path, 'w', encoding='utf-8') as f:
                                                f.write(new_content)
                                            self.file_contents[file_path] = new_content
                                            replacements += 1
                                            replacement_made = True
                                            print("Replaced block in {} (script match)".format(os.path.basename(file_path)))
                                            break
                        except Exception as e:
                            if self.debug:
                                print("  - Error in script matching: {}".format(e))
                    
                    # For meta tags
                    elif block_type == 'meta_tags':
                        # Similar approach as with script tags, but for meta tags
                        try:
                            meta_soup = BeautifulSoup(block['content'], 'html.parser')
                            meta_tags = meta_soup.find_all('meta')
                            
                            if meta_tags:
                                # Create a pattern that matches these meta tags with flexible whitespace
                                pattern = '\\s*'.join([re.escape(str(tag)) for tag in meta_tags])
                                matches = list(re.finditer(pattern, original_content, re.DOTALL))
                                
                                if matches:
                                    # Replace the first match
                                    match = matches[0]
                                    new_content = original_content[:match.start()] + include_statement + original_content[match.end():]
                                    with open(file_path, 'w', encoding='utf-8') as f:
                                        f.write(new_content)
                                    self.file_contents[file_path] = new_content
                                    replacements += 1
                                    replacement_made = True
                                    print("Replaced block in {} (meta tags match)".format(os.path.basename(file_path)))
                        except Exception as e:
                            if self.debug:
                                print("  - Error in meta tags matching: {}".format(e))
                
                # APPROACH 4: Fuzzy matching as a last resort
                if not replacement_made:
                    if self.debug:
                        print("  - Trying fuzzy matching")
                    
                    # Normalize whitespace in both content and block
                    try:
                        normalized_content = re.sub(r'\s+', ' ', original_content)
                        normalized_block = re.sub(r'\s+', ' ', block['content'])
                        
                        # Try to find the block with normalized whitespace
                        if normalized_block in normalized_content:
                            if self.debug:
                                print("  - Found normalized match")
                            
                            # Special case for navigation files - if the file itself is a navigation file,
                            # and it's small enough, just replace the entire content
                            if block_type == 'navigation' and 'navigation' in os.path.basename(file_path).lower():
                                if len(original_content) < len(block['content']) * 1.5:  # File is not much larger than block
                                    new_content = include_statement
                                    with open(file_path, 'w', encoding='utf-8') as f:
                                        f.write(new_content)
                                    self.file_contents[file_path] = new_content
                                    replacements += 1
                                    replacement_made = True
                                    print("Replaced block in {} (navigation file replacement)".format(os.path.basename(file_path)))
                            
                            # If not a special case or special case didn't work, try normal fuzzy matching
                            if not replacement_made:
                                # Find all occurrences of the normalized block
                                start_pos = 0
                                while True:
                                    pos = normalized_content.find(normalized_block, start_pos)
                                    if pos == -1:
                                        break
                                    
                                    # Calculate the approximate position in the original content
                                    content_before = normalized_content[:pos]
                                    original_start = len(re.sub(r'\s+', ' ', original_content[:len(content_before) + 20]).rstrip())
                                    
                                    # Try to find the exact block in the original content around this position
                                    found = False
                                    for i in range(max(0, original_start - 100), min(len(original_content), original_start + 100)):
                                        # Try different lengths to account for whitespace differences
                                        for length in range(len(block['content']), len(block['content']) + 100):
                                            if i + length <= len(original_content):
                                                candidate = original_content[i:i+length]
                                                # Compare normalized versions
                                                if re.sub(r'\s+', ' ', candidate) == normalized_block:
                                                    # Found a match with normalized whitespace
                                                    new_content = original_content[:i] + include_statement + original_content[i+length:]
                                                    with open(file_path, 'w', encoding='utf-8') as f:
                                                        f.write(new_content)
                                                    self.file_contents[file_path] = new_content
                                                    replacements += 1
                                                    replacement_made = True
                                                    print("Replaced block in {} (fuzzy match)".format(os.path.basename(file_path)))
                                                    found = True
                                                    break
                                        if found:
                                            break
                                    
                                    start_pos = pos + len(normalized_block)
                                    if found:
                                        break
                    except Exception as e:
                        if self.debug:
                            print("  - Error in fuzzy matching: {}".format(e))
                
                # APPROACH 5: Content-based matching for navigation blocks
                if not replacement_made and block_type in ['navigation']:
                    if self.debug:
                        print("  - Trying content-based navigation matching")
                    
                    try:
                        # Extract all menu items from the block
                        soup = BeautifulSoup(block['content'], 'html.parser')
                        menu_items = []
                        for a in soup.find_all('a'):
                            menu_items.append((a.get('href', ''), a.get_text().strip()))
                        
                        if menu_items and len(menu_items) >= 3:  # At least 3 menu items to be confident
                            if self.debug:
                                print("  - Found {} menu items in block".format(len(menu_items)))
                            
                            # Create a pattern to find these menu items in sequence
                            file_soup = BeautifulSoup(original_content, 'html.parser')
                            
                            # Find potential navigation containers
                            potential_navs = file_soup.find_all(['nav', 'div', 'ul'], class_=re.compile(r'(nav|menu)', re.I))
                            if not potential_navs:  # If no nav with class, try any nav or ul
                                potential_navs = file_soup.find_all(['nav', 'ul'])
                            
                            if self.debug:
                                print("  - Found {} potential navigation containers".format(len(potential_navs)))
                            
                            for nav in potential_navs:
                                nav_links = [(a.get('href', ''), a.get_text().strip()) for a in nav.find_all('a')]
                                
                                # Calculate how many menu items match
                                matches = sum(1 for item in menu_items if item in nav_links)
                                match_ratio = matches / len(menu_items) if menu_items else 0
                                
                                if self.debug:
                                    print("  - Nav container has {} links, match ratio: {:.2f}".format(len(nav_links), match_ratio))
                                
                                if match_ratio >= 0.7:  # At least 70% of menu items match
                                    # Found a match, replace it
                                    match_str = str(nav)
                                    if match_str in original_content:
                                        new_content = original_content.replace(match_str, include_statement)
                                        with open(file_path, 'w', encoding='utf-8') as f:
                                            f.write(new_content)
                                        self.file_contents[file_path] = new_content
                                        replacements += 1
                                        replacement_made = True
                                        print("Replaced block in {} (menu content match, ratio: {:.2f})".format(os.path.basename(file_path), match_ratio))
                                        break
                    except Exception as e:
                        if self.debug:
                            print("  - Error in content-based navigation matching: {}".format(e))
                
                # APPROACH 6: Special case for navigation files
                if not replacement_made and block_type == 'navigation' and 'navigation' in os.path.basename(file_path).lower():
                    if self.debug:
                        print("  - Trying special navigation file replacement")
                    
                    # If this is a navigation file (based on filename) and we've tried everything else,
                    # just replace the entire content as a last resort
                    try:
                        # Only do this if the file is small and likely to be just a navigation component
                        if len(original_content) < 5000:  # Arbitrary size limit to avoid replacing large files
                            new_content = include_statement
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(new_content)
                            self.file_contents[file_path] = new_content
                            replacements += 1
                            replacement_made = True
                            print("Replaced block in {} (navigation file fallback)".format(os.path.basename(file_path)))
                    except Exception as e:
                        if self.debug:
                            print("  - Error in navigation file fallback: {}".format(e))
                
                if not replacement_made:
                    print("Warning: Could not find block in {}".format(os.path.basename(file_path)))
        
        print("Made {} replacements".format(replacements))
        return replacements
    
    def run(self):
        """
        Run the complete refactoring process.
        
        Returns:
            tuple: (number of files processed, number of common blocks, number of replacements)
        """
        self.scan_directory()
        self.identify_common_blocks()
        include_files = self.create_includes()
        replacements = self.apply_includes(include_files)
        
        return len(self.php_files), len(self.common_blocks), replacements


def are_adjacent_siblings(elem1, elem2):
    """
    Check if two BeautifulSoup elements are adjacent siblings in the HTML.
    
    Args:
        elem1: First BeautifulSoup element
        elem2: Second BeautifulSoup element
        
    Returns:
        bool: True if they are adjacent siblings, False otherwise
    """
    # Get the next sibling of elem1, skipping whitespace
    next_sibling = elem1.next_sibling
    while next_sibling and isinstance(next_sibling, str) and next_sibling.strip() == '':
        next_sibling = next_sibling.next_sibling
    
    # Check if the next non-whitespace sibling is elem2
    return next_sibling == elem2


def extract_php_includes(domain, download_path, min_block_size=50, similarity_threshold=0.9, min_occurrences=2, debug=False):
    """
    Extract common blocks from PHP files and replace them with include statements.
    
    Args:
        domain (str): Domain name
        download_path (str): Path to downloaded files
        min_block_size (int): Minimum size in characters for a block to be considered
        similarity_threshold (float): Threshold for considering blocks similar (0.0-1.0)
        min_occurrences (int): Minimum number of occurrences for a block to be extracted
        debug (bool): Enable detailed debugging output
    
    Returns:
        tuple: (number of files processed, number of common blocks, number of replacements)
    """
    print("\nExtracting common blocks and creating PHP includes for {}...".format(domain))
    
    refactor = PHPRefactor(
        download_path,
        min_block_size=min_block_size,
        similarity_threshold=similarity_threshold,
        min_occurrences=min_occurrences,
        debug=debug
    )
    
    num_files, num_blocks, num_replacements = refactor.run()
    
    print("\nPHP Include Summary for {}:".format(domain))
    print("  Files processed: {}".format(num_files))
    print("  Common blocks found: {}".format(num_blocks))
    print("  Replacements made: {}".format(num_replacements))
    
    if num_blocks > 0:
        print("\nIncludes created in: {}".format(refactor.includes_dir))
        
    return num_files, num_blocks, num_replacements
