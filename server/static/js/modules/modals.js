export function markModalDirty(modalId) {
    const m = document.getElementById(modalId);
    if (m) m.dataset.dirty = 'true';
}

export function clearModalDirty(modalId) {
    const m = document.getElementById(modalId);
    if (m) m.dataset.dirty = 'false';
}

export function checkModalDiscard(modalId) {
    const m = document.getElementById(modalId);
    if (m && m.dataset.dirty === 'true') {
        return confirm("You have unsaved changes. Discard?");
    }
    return true;
}
const modalDirtyStates = {};




export function handleBackdropClick(e, modalId) {
    if (e.target.id === modalId) {
        if (!checkModalDiscard(modalId)) {
            return;
        }
        clearModalDirty(modalId);
        document.getElementById(modalId).style.display = 'none';
    }
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const openModals = [
            'location-modal', 'probe-modal', 'schedule-modal',
            'alert-rule-modal', 'maintenance-modal', 'channel-modal',
            'simulate-alert-modal', 'resolve-alert-modal', 'alert-detail-modal', 'evidence-modal'
        ];
        for (const mId of openModals) {
            const el = document.getElementById(mId);
            if (el && el.style.display !== 'none' && el.style.display !== '') {
                if (!checkModalDiscard(mId)) {
                    return;
                }
                clearModalDirty(mId);
                el.style.display = 'none';
                break;
            }
        }
        if (document.body.classList.contains('wallboard-fullscreen')) {
            toggleFullscreenMode();
        }
    } else if (e.key === 'ArrowRight') {
        if (currentSlideIndex === 4) nextGrafanaSub();
        else nextSlide();
    } else if (e.key === 'ArrowLeft') {
        if (currentSlideIndex === 4) prevGrafanaSub();
        else prevSlide();
    } else if (e.key === ' ') {
        togglePlayPause();
    }
});
