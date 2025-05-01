        // Responsive logo size function
        function adjustLogoSize() {
            const logo = document.getElementById('nav-logo');
            const windowWidth = window.innerWidth;
            
            // Calculate logo size based on window width
            // For example, scale between 20px and 150px based on screen width
            const minWidth = 50;
            const maxWidth = 100;
            const minScreenWidth = 320;   // Small mobile screen
            const maxScreenWidth = 1920;  // Large desktop screen
            
            // Calculate responsive width with constraints
            let logoWidth = minWidth + (windowWidth - minScreenWidth) * 
                (maxWidth - minWidth) / (maxScreenWidth - minScreenWidth);
                
            // Enforce min/max constraints
            logoWidth = Math.min(Math.max(logoWidth, minWidth), maxWidth);
            
            // Set the logo width
            logo.style.width = logoWidth + 'px';
        }
        
        // Call the function when page loads and when window is resized
        window.addEventListener('load', adjustLogoSize);
        window.addEventListener('resize', adjustLogoSize);