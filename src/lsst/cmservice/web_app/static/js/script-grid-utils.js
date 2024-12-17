// list of statuses to reset to if current status is failed or rejected
const resetFromRejected = {
    WAITING: 0,
    READY: 1,
    PREPARED: 2
};
// list of statuses to reset to if current status is reviewable
const resetFromReviewable = {
    ACCEPTED: 5,
    REJECTED: -3,
};

const updateStatus = async () => {
    const rowIndex = parseInt(document.querySelector("#rowIndex").innerText);
    const newStatus = parseInt(document.querySelector("#targetStatus").value);
    const fullname = String(document.querySelector("#scriptFullname").innerText)
    const scriptId = scriptGridApi.getRowNode(rowIndex).data.id;

    let url;
    let resetJson = null;

    // accept script
    if(newStatus === resetFromReviewable.ACCEPTED){
        url = `/cm-service/v1/script/action/${scriptId}/accept`;
    }
    // reject script
    else if(newStatus === resetFromReviewable.REJECTED){
        url = `/cm-service/v1/script/action/${scriptId}/reject`;
    }
    // reset script
    else {
        let resetObj = {
            fullname: fullname,
            status: newStatus,
        };

        resetJson = JSON.stringify(resetObj);
        url = reset_script_endpoint;
    }

    // send request
    const response = await fetch(url, {
        method: "POST",
        body: resetJson,
        headers: {
            "Content-Type": "application/json"
        }
    });

    if(response.ok) {
        // update script status in grid
        scriptGridApi
            .getRowNode(rowIndex)
            .setDataValue("status", document.querySelector("#targetStatus").selectedOptions[0].text);
        // refresh grid cells on client side to disable/enable reset button according to new status
        scriptGridApi.refreshCells({
            force: true,
            suppressFlash: false,
          });
        resetScriptModal.close();
    } else {
        resetScriptModal.close();
        errorModal.showModal();
        errorMessage.innerText = JSON.parse(await response.text()).detail;
    }
};

const readScriptLog = async (logURL) => {
    const url = "/web_app/read-script-log";
    const res  = await fetch(url, {
        method: "POST",
        body: JSON.stringify({ log_path: logURL}),
        headers: {
            "Content-Type": "application/json"
        }
    });
    if(!res.ok) {
        errorModal.showModal();
        errorMessage.innerText = JSON.parse(await res.text()).detail;
    } else {
        let response = await res.json()
        document.querySelector('#scriptLogContent').value = response.content;
        scriptLogModal.showModal();
    }
};

const fillTargetStatusDropdown = (statusEnum) => {
    let statusDropdown = document.querySelector("#targetStatus");
    statusDropdown.options.length = 0;
    Object.keys(statusEnum).forEach(state => {
        let option = document.createElement('option');
        option.setAttribute('value', statusEnum[state]);
        option.innerText = state;
        statusDropdown.add(option);
    });
};

class ResetButtonCellRenderer {
    init(params) {
        this.params = params;
        this.eGui = document.createElement('div');

        let gridShowLogBtn = document.createElement('button');
        gridShowLogBtn.innerText = "Show Log";
        if(params.data.log_url){
            gridShowLogBtn.setAttribute("class", 'mt-2 rounded bg-white px-2 py-1 text-xs font-semibold text-teal-700 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50');
            gridShowLogBtn.addEventListener('click', async () => await readScriptLog(params.data.log_url));
            gridShowLogBtn.disabled = false;
        } else {
            gridShowLogBtn.setAttribute("class", 'mt-2 rounded bg-white px-2 py-1 text-xs font-semibold text-gray-500 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50');
            gridShowLogBtn.disabled = true;
        }
        this.eGui.appendChild(gridShowLogBtn);

        let resetBtn = document.createElement('button');
        // change button text and also show/hide according to status
        let currentStatus = params.data.status;
        this.eGui.appendChild(resetBtn);

        if(currentStatus === "FAILED" || currentStatus === "REJECTED") {
            resetBtn.innerText = 'Reset';
        } else if(currentStatus === "REVIEWABLE") {
            resetBtn.innerText = 'Review';
        } else {
            // button is hidden if the current status isn't FAILED/REJECTED/REVIEWABLE
            resetBtn.hidden = true;
            return;
        }
        // show reset/review button
        resetBtn.hidden = false;
        resetBtn.setAttribute('class', 'ml-2 mt-2 rounded bg-white px-2 py-1 text-xs font-semibold text-teal-700 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50');

        resetBtn.addEventListener('click', () => {
            document.querySelector("#rowIndex").innerText = params.node.rowIndex;
             document.querySelector("#scriptFullname").innerText = params.data.fullname;

             // show script log path and button if it isn't null, otherwise show "-" and hide button
             const scriptLogElement = document.querySelector("#scriptLogUrl");
             if(params.data.log_url) {
                 scriptLogElement.innerText = params.data.log_url;
                 showLogBtn.hidden = false;
             } else {
                 scriptLogElement.innerText = "-";
                 showLogBtn.hidden = true;
             }
             showLogBtn.addEventListener("click", async() => await readScriptLog(params.data.log_url));

             // create target status dropdown according to current status
             let currentStatus = params.data.status;
             if(currentStatus === "FAILED" || currentStatus === "REJECTED"){
                 document.querySelector('#reset-modal-title').innerText = "Reset Script";
                 fillTargetStatusDropdown(resetFromRejected);
             } else if (currentStatus === "REVIEWABLE") {
                 document.querySelector('#reset-modal-title').innerText = "Review Script";
                 fillTargetStatusDropdown(resetFromReviewable);
             }
             resetScriptModal.showModal();
        });

    }

    getGui() {
        return this.eGui;
  }
}


const resetScriptModal = document.querySelector("#modalDialog");

const closeResetModalBtn = document.querySelector("[close-reset-modal]");
closeResetModalBtn.addEventListener("click", () => resetScriptModal.close());

const confirmResetBtn = document.querySelector("[confirm-reset]");
confirmResetBtn.addEventListener("click", updateStatus);

const showLogBtn = document.querySelector("#showLogBtn");

const errorModal = document.querySelector("#errorModal");
const closeErrModalBtn = document.querySelector("[close-error-modal]");
closeErrModalBtn.addEventListener("click", () => errorModal.close());
const errorMessage = document.querySelector("[error-message]")

const scriptLogModal = document.querySelector("#scriptLogModal");
const closeLogModalBtn = document.querySelector("[close-log-modal]");
closeLogModalBtn.addEventListener("click", () => scriptLogModal.close());
