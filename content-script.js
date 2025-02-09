function getStorage(key) {
    return new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ action: 'getStorage', key: key }, (response) => {
            if (chrome.runtime.lastError) {
                reject(chrome.runtime.lastError);
            } else {
                resolve(response.data);
            }
        });
    });
}

function setStorage(key, value) {
    return new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ action: 'setStorage', key: key, value: value }, (response) => {
            if (chrome.runtime.lastError) {
                reject(chrome.runtime.lastError);
            } else {
                resolve(response.status);
            }
        });
    });
}

// Example usage
getStorage('exampleKey').then(data => {
    console.log('Stored data:', data);
}).catch(error => {
    console.error('Error accessing storage:', error);
});

setStorage('exampleKey', 'exampleValue').then(status => {
    console.log('Storage set status:', status);
}).catch(error => {
    console.error('Error setting storage:', error);
});