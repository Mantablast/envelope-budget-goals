chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'getStorage') {
        const data = localStorage.getItem(request.key);
        sendResponse({ data: data });
    } else if (request.action === 'setStorage') {
        localStorage.setItem(request.key, request.value);
        sendResponse({ status: 'success' });
    }
    return true; // Keep the message channel open for sendResponse
});