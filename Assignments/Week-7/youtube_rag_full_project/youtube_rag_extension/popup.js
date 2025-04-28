document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements with error handling
    const searchButton = document.getElementById('searchButton');
    const searchQuery = document.getElementById('searchQuery');
    const resultsDiv = document.getElementById('results');
    const statusDiv = document.getElementById('status');

    // Create loading element if it doesn't exist
    let loadingDiv = document.getElementById('loading');
    if (!loadingDiv) {
        loadingDiv = document.createElement('div');
        loadingDiv.id = 'loading';
        loadingDiv.className = 'loading';
        loadingDiv.innerHTML = '<div class="spinner"></div><p>Processing video and searching...</p>';
        loadingDiv.style.display = 'none';
        document.body.appendChild(loadingDiv);
    }

    // Validate required DOM elements
    if (!searchButton || !searchQuery || !resultsDiv || !statusDiv) {
        console.error('Required DOM elements not found');
        if (statusDiv) {
            statusDiv.textContent = 'Error: Extension failed to initialize';
            statusDiv.className = 'status error';
        }
        return;
    }

    // Add some CSS for the loading spinner
    const style = document.createElement('style');
    style.textContent = `
        .loading {
            text-align: center;
            padding: 20px;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #4285f4;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .result-item {
            margin-bottom: 10px;
            padding: 10px;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
        }
        .result-header {
            display: flex;
            align-items: center;
            margin-bottom: 5px;
        }
        .result-number {
            font-weight: bold;
            margin-right: 10px;
        }
        .timestamp-button {
            background-color: #4285f4;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 3px 8px;
            cursor: pointer;
            margin-right: 10px;
        }
        .timestamp-button:hover {
            background-color: #3367d6;
        }
        .score {
            font-size: 0.8em;
            color: #666;
        }
        .result-content {
            margin-top: 5px;
            line-height: 1.4;
        }
    `;
    document.head.appendChild(style);

    // Get the current tab's URL
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
        const currentTab = tabs[0];
        if (!currentTab?.url?.includes('youtube.com/watch')) {
            resultsDiv.innerHTML = '<p class="error">Please open a YouTube video first.</p>';
            searchButton.disabled = true;
            return;
        }
    });

    searchButton.addEventListener('click', async function() {
        const query = searchQuery.value.trim();
        if (!query) {
            statusDiv.textContent = 'Please enter a search query.';
            statusDiv.className = 'status error';
            return;
        }

        // Get current tab URL
        const tabs = await chrome.tabs.query({active: true, currentWindow: true});
        const currentTab = tabs[0];
        const videoUrl = currentTab?.url;

        if (!videoUrl?.includes('youtube.com/watch')) {
            statusDiv.textContent = 'Please open a YouTube video first.';
            statusDiv.className = 'status error';
            return;
        }

        // Show loading state
        loadingDiv.style.display = 'block';
        resultsDiv.style.display = 'none';
        statusDiv.style.display = 'none';
        searchButton.disabled = true;

        try {
            console.log('Sending request to backend:', {
                user_input: query,
                url: videoUrl
            });
            
            // Make API request
            const response = await fetch('http://localhost:8000/agent', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_input: query,
                    url: videoUrl
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('Server response:', data);

            // Parse the result
            let results = [];
            if (data.result) {
                try {
                    // Try to parse the result as JSON if it's a string
                    let resultObj;
                    if (typeof data.result === 'string') {
                        try {
                            resultObj = JSON.parse(data.result);
                        } catch (e) {
                            // If it's not valid JSON, check if it contains JSON
                            const jsonMatch = data.result.match(/\{.*\}/s);
                            if (jsonMatch) {
                                try {
                                    resultObj = JSON.parse(jsonMatch[0]);
                                } catch (e2) {
                                    console.error('Failed to extract JSON from string:', e2);
                                    resultObj = { message: data.result };
                                }
                            } else {
                                resultObj = { message: data.result };
                            }
                        }
                    } else {
                        resultObj = data.result;
                    }
                    
                    // Check for error status
                    if (resultObj.status === 'error') {
                        throw new Error(resultObj.message || 'Unknown error occurred');
                    }

                    // Extract results based on response format
                    if (resultObj.results && Array.isArray(resultObj.results)) {
                        results = resultObj.results;
                    } else if (resultObj.data && resultObj.data.results) {
                        results = resultObj.data.results;
                    }

                    // Format and display results
                    if (results.length > 0) {
                        const resultsHtml = results.map((result, index) => {
                            const timestamp = result.timestamp || '00:00';
                            const score = result.score ? `(Score: ${(result.score * 100).toFixed(1)}%)` : '';
                            const content = result.content || result.text || 'No content available';
                            
                            return `
                                <div class="result-item">
                                    <div class="result-header">
                                        <span class="result-number">${index + 1}.</span>
                                        <button class="timestamp-button" data-start="${result.start || 0}">
                                            ${timestamp}
                                        </button>
                                        <span class="score">${score}</span>
                                    </div>
                                    <div class="result-content">${content}</div>
                                </div>
                            `;
                        }).join('');

                        resultsDiv.innerHTML = `
                            <div class="results-header">
                                <h3>Found ${results.length} relevant segments</h3>
                                <p class="query-time">${resultObj.query_time ? `(Search took ${resultObj.query_time.toFixed(2)}s)` : ''}</p>
                            </div>
                            <div class="results-list">
                                ${resultsHtml}
                            </div>
                        `;

                        // Add click handlers for timestamp buttons
                        document.querySelectorAll('.timestamp-button').forEach(button => {
                            button.addEventListener('click', function() {
                                const startTime = this.dataset.start;
                                console.log('Seeking to time:', startTime);
                                chrome.tabs.sendMessage(currentTab.id, {
                                    action: 'seekTo',
                                    time: startTime
                                }, function(response) {
                                    console.log('Response from content script:', response);
                                });
                            });
                        });

                        statusDiv.textContent = `Found ${results.length} relevant segments`;
                        statusDiv.className = 'status success';
                    } else {
                        resultsDiv.innerHTML = '<p class="no-results">No results found for your query.</p>';
                        statusDiv.textContent = 'No results found';
                        statusDiv.className = 'status error';
                    }
                } catch (parseError) {
                    console.error('Error parsing results:', parseError);
                    // Display raw result if parsing failed
                    resultsDiv.innerHTML = `<p>Raw result: ${data.result}</p>`;
                    statusDiv.textContent = 'Error parsing search results';
                    statusDiv.className = 'status error';
                }
            } else {
                resultsDiv.innerHTML = '<p class="no-results">No results found.</p>';
                statusDiv.textContent = 'No results found';
                statusDiv.className = 'status error';
            }

        } catch (error) {
            console.error('Error:', error);
            resultsDiv.innerHTML = `<p class="error">Error: ${error.message}</p>`;
            statusDiv.textContent = `Error: ${error.message}`;
            statusDiv.className = 'status error';
        } finally {
            // Hide loading state
            loadingDiv.style.display = 'none';
            resultsDiv.style.display = 'block';
            searchButton.disabled = false;
        }
    });

    // Add keyboard support
    searchQuery.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            searchButton.click();
        }
    });
});
