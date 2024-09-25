// script.js

const socket = io();

// Open and close settings modal
const openSettingsWaitingBtn = document.getElementById(
  "openSettingsWaitingBtn"
);
const openSettingsOrderBtn = document.getElementById("openSettingsOrderBtn");
const closeSettingsBtn = document.getElementById("closeSettingsBtn");
const settingsModal = document.getElementById("settingsModal");

// Open modal for both Waiting Time and Order Waiting Time
openSettingsWaitingBtn.addEventListener("click", () => {
  document.getElementById("setTime").parentElement.style.display = "block";
  document.getElementById("setOrderTime").parentElement.style.display = "none";
  settingsModal.classList.remove("hidden");
});
openSettingsOrderBtn.addEventListener("click", () => {
  document.getElementById("setTime").parentElement.style.display = "none";
  document.getElementById("setOrderTime").parentElement.style.display = "block";
  settingsModal.classList.remove("hidden");
});

closeSettingsBtn.addEventListener("click", () => {
  settingsModal.classList.add("hidden");
});

// Handle settings form submission
const settingsForm = document.getElementById("settingsForm");
settingsForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const setTime = document.getElementById("setTime").value;
  const setOrderTime = document.getElementById("setOrderTime").value;

  const dataToSend = setTime ? { setTime } : { setOrderTime }; // Send only the relevant data

  fetch("/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dataToSend),
  })
    .then((response) => response.json())
    .then((data) => {
      console.log(data.message);
      settingsModal.classList.add("hidden");
      socket.emit("update_settings", dataToSend); // Trigger settings update
    });
});

// Fetch items and populate select options
fetch("/items")
  .then((response) => response.json())
  .then((data) => {
    const itemSelect = document.getElementById("itemSelect");
    const items = data;
    items.cakes.forEach((item) => {
      const option = document.createElement("option");
      option.value = item;
      option.textContent = item;
      itemSelect.appendChild(option);
    });
    items.coffee.forEach((item) => {
      const option = document.createElement("option");
      option.value = item;
      option.textContent = item;
      itemSelect.appendChild(option);
    });
  });

// Update waiting times table
socket.on("update_waiting_times", (waitingTimes) => {
  const waitingTimesBody = document.getElementById("waitingTimesBody");
  waitingTimesBody.innerHTML = ""; // Clear existing rows
  Object.entries(waitingTimes).forEach(([person, info]) => {
    const row = document.createElement("tr");
    const waitingTimeClass = info.waiting_time.includes("EXCEEDED")
      ? "text-red-500 font-bold"
      : "";
    const orderWaitingTimeClass = info.order_waiting_time.includes("EXCEEDED")
      ? "text-red-500 font-bold"
      : "";

    row.innerHTML = `
      <td class="px-4 py-2 border-b">${person}</td>
      <td class="px-4 py-2 border-b ${waitingTimeClass}">${info.waiting_time}</td>
      <td class="px-4 py-2 border-b ${orderWaitingTimeClass}">${info.order_waiting_time}</td>
      <td class="px-4 py-2 border-b">
        ${info.orders}
        <button
          class="bg-red-500 text-white py-1 px-3 rounded-md hover:bg-red-600 ml-2 clear-btn"
          data-person="${person}"
          data-order="${info.orders}">
          Clear
        </button>
      </td>
    `;
    waitingTimesBody.appendChild(row);
  });

  attachClearButtonListeners();

  function attachClearButtonListeners() {
    document.querySelectorAll(".clear-btn").forEach((button) => {
      button.addEventListener("click", (event) => {
        const person = event.target.getAttribute("data-person");
        const order = event.target.getAttribute("data-order");
        clearOrder(person, order);
      });
    });
  }

  function removeOrderFromUI(person, order) {
    const waitingTimesBody = document.getElementById("waitingTimesBody");
    const rows = waitingTimesBody.getElementsByTagName("tr");

    for (let row of rows) {
      const personCell = row.cells[0].textContent;
      const orderCell = row.cells[3].textContent;

      if (personCell === person && orderCell.includes(order)) {
        waitingTimesBody.removeChild(row);
        break;
      }
    }
  }

  const personSelect = document.getElementById("personSelect");
  const currentSelection = personSelect.value;

  personSelect.innerHTML = "";
  Object.keys(waitingTimes).forEach((person) => {
    const option = document.createElement("option");
    option.value = person.split(" ")[1];
    option.textContent = person;
    personSelect.appendChild(option);
  });

  if (currentSelection) {
    personSelect.value = currentSelection;
  }
});

const orderForm = document.getElementById("orderForm");
orderForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const person = document.getElementById("personSelect").value;
  const item = document.getElementById("itemSelect").value;
  fetch("/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ person_id: parseInt(person), order: item }),
  })
    .then((response) => response.json())
    .then((data) => {
      console.log(data.message);
      socket.emit("update_waiting_times");
    });
});

socket.emit("update_waiting_times");
