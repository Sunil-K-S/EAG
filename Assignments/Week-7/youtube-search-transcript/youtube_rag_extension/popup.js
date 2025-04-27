
document.getElementById("ask").onclick = async () => {
  const query = document.getElementById("query").value;
  chrome.runtime.sendMessage({ type: "GET_URL" }, async response => {
    const url = response.url;
    const res = await fetch("http://localhost:8000/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_url: url, query })
    });
    const data = await res.json();
    document.getElementById("result").innerHTML = data.results
      .map(r => `<div><b>${r.timestamp}</b> - ${r.text}</div>`)
      .join("");
  });
};
