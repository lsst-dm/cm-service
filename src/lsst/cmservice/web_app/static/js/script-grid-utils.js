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

const updateStatus = () => {
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
    let xhr = new XMLHttpRequest();
    xhr.open('POST', url, true);
    xhr.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
    xhr.onload = function () {
        if (xhr.status === 201) {
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
            errorMessage.innerText = JSON.parse(xhr.responseText).detail;
        }
    };
    xhr.onerror = function () {
        resetScriptModal.close();
        errorModal.showModal();
        errorMessage.innerText = xhr.responseText;
    };
    xhr.send(resetJson);

};

const readScriptLog = (log_url) => {

    const xhr = new XMLHttpRequest();

    const url = "/web_app/read-script-log";

    xhr.onreadystatechange = function () {
        if (xhr.readyState === XMLHttpRequest.DONE) {
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                // show file content from response in the textarea
                document.querySelector('#scriptLogContent').value = response.content;
                scriptLogModal.showModal();
            } else {
                errorModal.showModal();
                errorMessage.innerText = JSON.parse(xhr.responseText).detail;
            }
        }
    };

    xhr.open("POST", url, true);

    xhr.setRequestHeader("Content-Type", "application/json");

    const requestData = JSON.stringify({ log_path: log_url});
    xhr.send(requestData);
}

class ResetButtonCellRenderer {
    init(params) {
        this.params = params;
        this.eGui = document.createElement('button');
        // change button text and also enable/disable according to status
        let currentStatus = params.data.status;
        if(currentStatus === "FAILED" || currentStatus === "REJECTED") {
            this.eGui.innerText = 'Reset';
        } else if(currentStatus === "REVIEWABLE") {
            this.eGui.innerText = 'Review';
        } else {
            // button is disabled if the current status isn't FAILED/REJECTED/REVIEWABLE
            this.eGui.innerText = 'Reset';
            this.eGui.disabled = true;
            this.eGui.setAttribute('class', 'mt-2 rounded bg-white px-2 py-1 text-xs font-semibold text-gray-500 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50');
            return;
        }
        // enable reset/review button
        this.eGui.disabled = false;
        this.eGui.setAttribute('class', 'mt-2 rounded bg-white px-2 py-1 text-xs font-semibold text-teal-700 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50');

        this.eGui.addEventListener('click', () => {
            document.querySelector("#rowIndex").innerText = params.node.rowIndex;
             document.querySelector("#scriptFullname").innerText = params.data.fullname;

             // show script log path if it isn't null, otherwise show "-"
             const scriptLogElement = document.querySelector("#scriptLogUrl");
             scriptLogElement.innerHTML = "";
             if(params.data.log_url) {
                 let logUrl = document.createElement('span');
                 logUrl.innerText = params.data.log_url;
                 scriptLogElement.appendChild(logUrl);

                 // add a button to show log content dialog
                 let showLogBtn = document.createElement('button');
                 showLogBtn.innerText = 'Show Log';
                 showLogBtn.setAttribute('class', 'mt-2 rounded bg-white px-2 py-1 text-xs font-semibold text-teal-700 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50');
                 showLogBtn.addEventListener('click', (e) => {
                     readScriptLog(params.data.log_url);
                 });
                 scriptLogElement.appendChild(showLogBtn);

             } else {
                 scriptLogElement.innerText = "-";
             }
             // create target status dropdown according to current status
             let statusDropdown = document.querySelector("#targetStatus");
             statusDropdown.options.length = 0;
             let currentStatus = params.data.status;
             if(currentStatus === "FAILED" || currentStatus === "REJECTED"){
                 document.querySelector('#reset-modal-title').innerText = "Reset Script";
                 Object.keys(resetFromRejected).forEach(state => {
                     let option = document.createElement('option');
                     option.setAttribute('value', resetFromRejected[state]);
                     option.innerText = state;
                     statusDropdown.add(option);
                 });
             } else if (currentStatus === "REVIEWABLE") {
                 document.querySelector('#reset-modal-title').innerText = "Review Script";
                 Object.keys(resetFromReviewable).forEach(state => {
                     let option = document.createElement('option');
                     option.setAttribute('value', resetFromReviewable[state]);
                     option.innerText = state;
                     statusDropdown.add(option);
                 });
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

const errorModal = document.querySelector("#errorModal");
const closeErrModalBtn = document.querySelector("[close-error-modal]");
closeErrModalBtn.addEventListener("click", () => errorModal.close());
const errorMessage = document.querySelector("[error-message]")

const scriptLogModal = document.querySelector("#scriptLogModal");
const closeLogModalBtn = document.querySelector("[close-log-modal]");
closeLogModalBtn.addEventListener("click", () => scriptLogModal.close());
