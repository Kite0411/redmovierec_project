    <script>
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
