import { toggleSidebar, toggleTheme, switchView, goToSlide, nextSlide, prevSlide, togglePlayPause, toggleFullscreenMode, prevGrafanaSub, nextGrafanaSub, goToGrafanaSub } from './main.js';
// Add event delegation
document.addEventListener('click', (e) => {
    let target = e.target;
    while (target && target !== document.body) {
        if (target.hasAttribute('data-action')) {
            const action = target.getAttribute('data-action');
            // evaluate the action string, it's mostly func() or func(args)
            try {
                // simple eval because these are controlled by us
                // alternatively could parse it.
                // It is safer to parse it
                const match = action.match(/^([a-zA-Z0-9_]+)\((.*)\)$/);
                if (match) {
                    const funcName = match[1];
                    const argsStr = match[2];
                    let args = [];
                    if (argsStr) {
                         // crude parsing of args, assume simple strings or numbers
                         args = argsStr.split(',').map(s => {
                            s = s.trim();
                            if (s.startsWith("'") && s.endsWith("'")) return s.slice(1, -1);
                            if (s.startsWith('"') && s.endsWith('"')) return s.slice(1, -1);
                            if (s === 'true') return true;
                            if (s === 'false') return false;
                            if (!isNaN(s)) return Number(s);
                            return window[s]; // variables
                         });
                    }
                    if (window[funcName] && typeof window[funcName] === 'function') {
                        window[funcName](...args);
                    } else {
                         console.warn("Function not found on window:", funcName);
                    }
                }

            } catch (err) {
                 console.error("Error executing data-action", action, err);
            }
            // Prevent default page scroll on buttons and dummy links
            const tag = target.tagName.toLowerCase();
            const href = target.getAttribute('href');
            if (tag === 'button' || tag === 'a' && (href === '#' || href === 'javascript:void(0)')) {
                 e.preventDefault();
            }
            return;
        }
        target = target.parentElement;
    }
});

// Keydown event listener for Enter and Space key accessibility
document.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' && e.key !== ' ' && e.key !== 'Spacebar') {
        return;
    }

    let target = e.target;
    while (target && target !== document.body) {
        if (target.hasAttribute('data-action') || target.getAttribute('role') === 'button' || target.hasAttribute('tabindex') || target.tagName.toLowerCase() === 'button') {
            if (e.key === ' ' || e.key === 'Spacebar') {
                e.preventDefault(); // Prevent page scroll on Space press
                target.click();
            } else if (e.key === 'Enter' && target.tagName.toLowerCase() !== 'button') {
                // Native buttons handle Enter click automatically; for non-button controls, trigger click
                target.click();
            }
            return;
        }
        target = target.parentElement;
    }
});
