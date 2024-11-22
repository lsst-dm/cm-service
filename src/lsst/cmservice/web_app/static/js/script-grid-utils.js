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
    if(newStatus === 5){
        url = `/cm-service/v1/script/action/${scriptId}/accept`;
    }
    // reject script
    else if(newStatus === -3){
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
        console.log(xhr.responseText);

        if (xhr.status === 201) {
            scriptGridApi.getRowNode(rowIndex).setDataValue("status", document.querySelector("#targetStatus").selectedOptions[0].text);
            scriptGridApi.refreshCells({
                force: true,
                suppressFlash: false,
              });
            resetScriptModal.close();
        } else {
            resetScriptModal.close();
            errorModal.showModal();
            errorMessage.innerText = 'Error accepting script!';
        }
    };
    xhr.onerror = function () {
        console.error("Request failed");
        alert('Error accepting script!');
        resetScriptModal.close();
    };
    xhr.send(resetJson);

};

class ResetButtonCellRenderer {
    init(params) {
        this.params = params;
        this.eGui = document.createElement('button');
        this.eGui.innerText = 'Reset';
        let currentStatus = params.data.status;

        if(currentStatus === "FAILED" || currentStatus === "REJECTED") {
            this.eGui.innerText = 'Reset';
        } else if(currentStatus === "REVIEWABLE") {
            this.eGui.innerText = 'Review';
        } else {
            this.eGui.disabled = true;
            this.eGui.setAttribute('class', 'mt-2 rounded bg-white px-2 py-1 text-xs font-semibold text-gray-500 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50');
            return;
        }

        this.eGui.disabled = false;
        this.eGui.setAttribute('class', 'mt-2 rounded bg-white px-2 py-1 text-xs font-semibold text-teal-700 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50');

        this.eGui.addEventListener('click', () => {
            document.querySelector("#rowIndex").innerText = params.node.rowIndex;
             document.querySelector("#scriptFullname").innerText = params.data.fullname;
             const scriptLogElement = document.querySelector("#scriptLogUrl");
             scriptLogElement.innerHTML = "";
             if(params.data.log_url) {
                 let logUrlHref = document.createElement('a');
                 logUrlHref.setAttribute('class', 'text-teal-700 underline underline-offset-4 decoration-1 hover:text-gray-500');
                 logUrlHref.href = params.data.log_url;
                 logUrlHref.innerText = params.data.log_url;
                 scriptLogElement.appendChild(logUrlHref);
             } else {
                 scriptLogElement.innerText = "-";
             }

             let statusDropdown = document.querySelector("#targetStatus");
             statusDropdown.options.length = 0;
             let currentStatus = params.data.status;
             if(currentStatus === "FAILED" || currentStatus === "REJECTED"){
                 document.querySelector('#modal-title').innerText = "Reset Script";
                 Object.keys(resetFromRejected).forEach(state => {
                     let option = document.createElement('option');
                     option.setAttribute('value', resetFromRejected[state]);
                     option.innerText = state;
                     statusDropdown.add(option);
                 });
             } else if (currentStatus === "REVIEWABLE") {
                 document.querySelector('#modal-title').innerText = "Review Script";
                 Object.keys(resetFromReviewable).forEach(state => {
                     let option = document.createElement('option');
                     option.setAttribute('value', resetFromReviewable[state]);
                     option.innerText = state;
                     statusDropdown.add(option);
                 });
             } else {
                 errorModal.showModal();
                 errorMessage.innerText = `Cannot reset a script from ${currentStatus} status`;
                 return;
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
