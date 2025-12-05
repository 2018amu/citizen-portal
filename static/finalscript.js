let lang = "en";
let services = [];
let categories = [];
let currentServiceName = "";
let currentSub = null;
let profile_id = null;

// -----------------------------
// LANGUAGE
// -----------------------------
function setLang(l) {
  lang = l;
  loadCategories();
}

// -----------------------------
// LOAD CATEGORIES
// -----------------------------
async function loadCategories() {
  try {
    const res = await fetch("/api/categories");
    if (!res.ok) throw new Error("Failed to load categories");

    categories = await res.json();
    const el = document.getElementById("category-list");
    el.innerHTML = "";

    categories.forEach((c) => {
      const btn = document.createElement("div");
      btn.className = "cat-item";
      btn.textContent = c.name?.[lang] || c.name?.en || c.id;
      btn.onclick = () => loadMinistriesInCategory(c);
      el.appendChild(btn);
    });
  } catch (err) {
    console.error("Categories load error:", err);
  }
}

// -----------------------------
// LOAD MINISTRIES
// -----------------------------
async function loadMinistriesInCategory(cat) {
  const subList = document.getElementById("sub-list");
  subList.innerHTML = "";
  document.getElementById("sub-title").innerText =
    cat.name?.[lang] || cat.name?.en || cat.id;

  try {
    const svcRes = await fetch("/api/services");
    if (!svcRes.ok) throw new Error("Failed to load services");

    const all = await svcRes.json();

    all
      .filter((s) => s.category === cat.id)
      .forEach((s) => {
        s.subservices?.forEach((sub) => {
          const li = document.createElement("li");
          li.textContent = sub.name?.[lang] || sub.name?.en || sub.id;
          li.onclick = () => loadQuestions(s, sub);
          subList.appendChild(li);
        });
      });
  } catch (err) {
    console.error("Error loading ministries:", err);
  }
}

// -----------------------------
// LOAD QUESTIONS
// -----------------------------
async function loadQuestions(service, sub) {
  currentServiceName = service.name?.[lang] || service.name?.en;
  currentSub = sub;

  const qList = document.getElementById("question-list");
  qList.innerHTML = "";
  document.getElementById("q-title").innerText =
    sub.name?.[lang] || sub.name?.en || sub.id;

  (sub.questions || []).forEach((q) => {
    const li = document.createElement("li");
    li.textContent = q.q?.[lang] || q.q?.en;
    li.onclick = () => showAnswer(service, sub, q);
    qList.appendChild(li);
  });
}

// -----------------------------
// SHOW ANSWER DETAILS
// -----------------------------
function showAnswer(service, sub, q) {
  let html = `
        <h3>${q.q?.[lang] || q.q?.en}</h3>
        <p>${q.answer?.[lang] || q.answer?.en}</p>
    `;

  if (q.downloads?.length) {
    html += `<p><b>Downloads:</b> ${q.downloads
      .map((d) => `<a href="${d}" target="_blank">${d.split("/").pop()}</a>`)
      .join(", ")}</p>`;
  }

  if (q.location) {
    html += `<p><b>Location:</b> <a href="${q.location}" target="_blank">View Map</a></p>`;
  }

  if (q.instructions) {
    html += `<p><b>Instructions:</b> ${q.instructions}</p>`;
  }

  html += `
        <p>
            <button onclick="alert('Download clicked')">Download</button>
            <button onclick="alert('Contact clicked')">Contact</button>
            <button onclick="alert('Apply clicked')">Apply</button>
        </p>
    `;

  document.getElementById("answer-box").innerHTML = html;

  // Engagement Logging
  fetch("/api/engagement", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: profile_id,
      question_clicked: q.q?.[lang] || q.q?.en,
      service: currentServiceName,
    }),
  });
}

// -----------------------------
// ADS
// -----------------------------
async function loadAds() {
  try {
    const res = await fetch("/api/ads");
    if (!res.ok) throw new Error("Failed to load ads");

    const ads = await res.json();
    const el = document.getElementById("ads-area");

    el.innerHTML = ads
      .map(
        (a) => `
            <div class="ad-card">
                <a href="${a.link || "#"}" target="_blank">
                    <h4>${a.title}</h4>
                    <p>${a.body || ""}</p>
                </a>
            </div>
        `
      )
      .join("");
  } catch (err) {
    console.error("Ads error:", err);
    document.getElementById("ads-area").innerHTML = "<p>No ads available.</p>";
  }
}

// -----------------------------
// CHAT PANEL
// -----------------------------
// function openChat() {
//     const panel = document.getElementById("chat-panel");
//     panel.style.display = "flex"; // must match flex in CSS
// }

// function closeChat() {
//     const panel = document.getElementById("chat-panel");
//     panel.style.display = "none";
// }

// // -----------------------------
// // HYBRID AI SEARCH CHAT
// // -----------------------------
// async function sendChat() {
//     const input = document.getElementById("chat-text");
//     const text = input.value.trim();
//     if (!text) return;

//     appendChat("user", text);
//     input.value = "";

//     try {
//         // const res = await fetch("/api/ai/search", {
//         //     method: "POST",
//         //     headers: { "Content-Type": "application/json" },
//         //     body: JSON.stringify({ query: text })
//         // });

//         // const data = await res.json();
//         const res = await fetch("/api/ai/search", {
//             method: "POST",
//             headers: { "Content-Type": "application/json" },
//             body: JSON.stringify({ query: text, top_k: 5 })
//         });
//         const data = await res.json();
//         appendChat("bot", data.answer || JSON.stringify(data.results));

//         let reply = "";

//         if (data.results?.length > 0) {
//             reply += "🔍 **Related Information:\n\n**";
//             data.results.forEach((r, i) => {
//                 reply += `${i + 1}. ${r.text || r.answer || r.question || JSON.stringify(r)}\n\n`;
//             });
//         } else {
//             reply = "❌ No related information found.";
//         }

//         appendChat("bot", reply);

//     } catch (err) {
//         appendChat("bot", "AI service unavailable.");
//     }

//     // Engagement logging
//     fetch("/api/engagement", {
//         method: "POST",
//         headers: { "Content-Type": "application/json" },
//         body: JSON.stringify({ user_id: profile_id, question_clicked: text, service: null })
//     });
// }

// function appendChat(sender, text, isHtml = false) {
//     const body = document.getElementById("chat-body");
//     if (!body) return;

//     const div = document.createElement("div");
//     div.className = "chat-msg " + (sender === "user" ? "user-msg" : "bot-msg");
//     if (isHtml) div.innerHTML = text;
//     else div.textContent = text;

//     body.appendChild(div);

//     // scroll into view
//     div.scrollIntoView({ behavior: "smooth", block: "end" });
// }
// const chatBody = document.getElementById("chat-body");
// new MutationObserver(() => {
//     chatBody.scrollTop = chatBody.scrollHeight;
// }).observe(chatBody, { childList: true });
// Append chat message
// function appendChat(sender, text, source = "") {
//   const body = document.getElementById("chat-body");
//   const div = document.createElement("div");

//   div.className = "chat-msg " + (sender === "user" ? "user-msg" : "bot-msg");

//   if (sender === "bot") {
//     // Show source if available
//     div.innerHTML = source
//       ? `<span class="chat-source">[${source.toUpperCase()}]</span>: ${text}`
//       : text;
//   } else {
//     div.innerText = text;
//   }

//   body.appendChild(div);
//   body.scrollTop = body.scrollHeight; // Auto-scroll
// }

// Send chat message to hybrid endpoint
// async function sendChat() {
//     const input = document.getElementById("chat-text");
//     const text = input.value.trim();
//     if (!text) return;

//     appendChat("user", text);
//     input.value = "";

//     try {
//         const res = await fetch("/api/ai/search", {
//             method: "POST",
//             headers: { "Content-Type": "application/json" },
//             body: JSON.stringify({ query: text, top_k: 5 })
//         });

//         const data = await res.json();

//         if (data.results && data.results.length > 0) {
//             // Show each result with proper source label
//             data.results.forEach(r => {
//                 let answer = r.answer || r.body || r.description || "";
//                 let display = answer || JSON.stringify(r);
//                 let source = r.source || "hybrid";
//                 appendChat("bot", display, source);
//             });
//         } else if (data.answer) {
//             appendChat("bot", data.answer, data.source || "ai");
//         } else {
//             appendChat("bot", "No results found.", "hybrid");
//         }
//     } catch (err) {
//         appendChat("bot", "AI service unavailable.", "error");
//         console.error(err);
//     }

//     // Engagement logging
//     if (profile_id) {
//         fetch("/api/engagement", {
//             method: "POST",
//             headers: { "Content-Type": "application/json" },
//             body: JSON.stringify({ user_id: profile_id, question_clicked: text, service: null })
//         });
//     }
// }



async function sendChat() {
    const input = document.getElementById("chat-text");
    const text = input.value.trim();
    if (!text) return;

    appendChat("user", text);
    input.value = "";

    try {
        const res = await fetch("/api/ai/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: text })
        });

        const data = await res.json();

        if (data.result) {
            let answer = data.result.answer || data.result.body || data.result.description || JSON.stringify(data.result);
            appendChat("bot", answer, data.result.source || data.source);
        } else {
            appendChat("bot", "No answer found.", "hybrid");
        }
    } catch (err) {
        appendChat("bot", "AI service unavailable.", "error");
        console.error(err);
    }
}
async function sendAIOnlyChat() {
    const input = document.getElementById("chat-text");
    const text = input.value.trim();
    if (!text) return;

    appendChat("user", text);
    input.value = "";

    try {
        const res = await fetch("/api/ai/ai_only_search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: text })
        });

        const data = await res.json();

        if (data.results && data.results.length > 0) {
            // Always display only the first and most accurate answer
            const answerObj = data.results[0];
            const answerText = answerObj.answer || "No answer available.";
            appendChat("bot", answerText, answerObj.source || "ai");
        } else {
            appendChat("bot", "No answer available.", "ai");
        }

    } catch (err) {
        appendChat("bot", "AI service unavailable.", "error");
        console.error(err);
    }

    // Optional: Engagement logging
    if (profile_id) {
        fetch("/api/engagement", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: profile_id, question_clicked: text, service: "ai_only" })
        });
    }
}



// ---------------- Helper to append messages ----------------
function appendChat(sender, message, source = "") {
    const chatContainer = document.getElementById("chat-container");
    if (!chatContainer) return;

    const msgDiv = document.createElement("div");
    msgDiv.className = `chat-msg ${sender}`;

    let label = source ? `[${source.toUpperCase()}]: ` : "";
    msgDiv.textContent = label + message;

    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}


// -----------------------------
// PROFILE MODAL
// -----------------------------
function showProfileModal() {
  document.getElementById("profile-modal").style.display = "flex";
}

function profileNext(step) {
  document.getElementById(`profile-step-${step}`).style.display = "none";
  document.getElementById(`profile-step-${step + 1}`).style.display = "block";
}

function profileBack(step) {
  document.getElementById(`profile-step-${step}`).style.display = "none";
  document.getElementById(`profile-step-${step - 1}`).style.display = "block";
}

async function profileSubmit() {
  try {
    const data1 = {
      name: document.getElementById("p_name").value,
      age: document.getElementById("p_age").value,
    };
    const data2 = {
      email: document.getElementById("p_email").value,
      phone: document.getElementById("p_phone").value,
    };
    const data3 = {
      job: document.getElementById("p_job").value,
    };

    let res = await fetch("/api/profile/step", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        step: "basic",
        data: { ...data1, email: data2.email },
      }),
    });

    let j = await res.json();
    if (!j.profile_id) {
      alert("Error creating profile!");
      return;
    }

    profile_id = j.profile_id;

    await fetch("/api/profile/step", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id, step: "contact", data: data2 }),
    });

    await fetch("/api/profile/step", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id, step: "employment", data: data3 }),
    });

    document.getElementById("profile-modal").style.display = "none";
    localStorage.setItem("profile_done", "1");
    alert("Profile saved successfully!");

    if (typeof loadRecommendedServices === "function") {
      loadRecommendedServices();
    }
  } catch (err) {
    console.error("Profile error:", err);
    alert("Error saving profile!");
  }
}

// -----------------------------
// RECOMMENDED SERVICES
// -----------------------------
async function loadRecommendedServices() {
  if (!profile_id) return;

  try {
    const res = await fetch(`/api/engagement?user_id=${profile_id}`);
    const engagements = await res.json();

    const serviceCount = {};
    engagements.forEach((e) => {
      if (e.service) {
        serviceCount[e.service] = (serviceCount[e.service] || 0) + 1;
      }
    });

    const topServices = Object.entries(serviceCount)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map((e) => e[0]);

    const el = document.getElementById("sub-list");
    el.innerHTML = "<h3>Recommended for you</h3>";

    topServices.forEach((s) => {
      const li = document.createElement("li");
      li.textContent = s;

      li.onclick = async () => {
        const svcRes = await fetch("/api/services");
        const all = await svcRes.json();

        const svc = all.find(
          (x) => x.name?.en === s || x.name?.si === s || x.name?.ta === s
        );

        if (svc?.subservices?.length > 0) {
          loadQuestions(svc, svc.subservices[0]);
        } else {
          alert("No related subservices found.");
        }
      };

      el.appendChild(li);
    });
  } catch (err) {
    console.error("Error loading recommended:", err);
  }
}

// -----------------------------
// PAGE LOAD
// -----------------------------
window.onload = async () => {
  await loadCategories();

  const svcRes = await fetch("/api/services");
  services = await svcRes.json();

  if (!localStorage.getItem("profile_done")) {
    showProfileModal();
  }
};

// -----------------------------
// CLOSE MODAL ON OUTSIDE CLICK
// -----------------------------
window.onclick = function (event) {
  const modal = document.getElementById("profile-modal");
  if (event.target === modal) {
    modal.style.display = "none";
  }
};
