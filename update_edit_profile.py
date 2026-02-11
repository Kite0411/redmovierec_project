#!/usr/bin/env python3
# Script to add auto-hide functionality to success/error messages in edit_profile.html

with open('moviehub/templates/pages/edit_profile.html', 'r', encoding='utf-8') as f:
    content = f.read()

auto_hide_script = '''    <script>
        // Auto-hide success and error messages after 3 seconds
        (function(){
            const errorDiv = document.querySelector('div[style*="FF6B6B"]');
            const successDiv = document.querySelector('div[style*="4CAF50"]');
            
            const hideAfter3Seconds = (element) => {
                if (element) {
                    setTimeout(() => {
                        element.style.transition = 'opacity 0.3s ease';
                        element.style.opacity = '0';
                        setTimeout(() => {
                            element.style.display = 'none';
                        }, 300);
                    }, 3000);
                }
            };
            
            hideAfter3Seconds(errorDiv);
            hideAfter3Seconds(successDiv);
        })();
    </script>

    <script>
        // Password toggle: switch input type between password/text for edit profile'''

# Find and replace
old_pattern = '''    <script>
        // Password toggle: switch input type between password/text for edit profile'''

if old_pattern in content:
    content = content.replace(old_pattern, auto_hide_script)
    with open('moviehub/templates/pages/edit_profile.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("✓ Updated edit_profile.html with auto-hide messages script (3 seconds)")
else:
    print("✗ Pattern not found - template structure may have changed")
