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
    let resetObj = {
        fullname: String(document.querySelector("#scriptFullname").innerText),
        status: parseInt(document.querySelector("#targetStatus").value),
    };

    let resetJson = JSON.stringify(resetObj);

    let xhr = new XMLHttpRequest();
    xhr.open('POST', reset_script_endpoint, true);
    xhr.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
    xhr.onload = function () {
        console.log(xhr.responseText);

        if (xhr.status === 201) {
            const rowIndex = Number(document.querySelector("#rowIndex").innerText);
            const newStatus = resetObj.status;
            scriptGridApi.getRowNode(rowIndex).setDataValue("status", newStatus);
            resetScriptModal.close();
        } else {
            resetScriptModal.close();
            errorModal.showModal();
            errorMessage.innerText = 'Error resetting script!';
        }
    };
    xhr.onerror = function () {
        console.error("Request failed");
        alert('Error resetting script!');
        resetScriptModal.close();
    };
    xhr.send(resetJson);
};

class ResetButtonCellRenderer {
    init(params) {
        this.params = params;
        this.eGui = document.createElement('button');
        this.eGui.innerText = 'Reset';
        this.eGui.setAttribute('class', 'mt-2 rounded bg-white px-2 py-1 text-xs font-semibold text-teal-700 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50');

        this.eGui.addEventListener('click', () => {

         document.querySelector("#rowIndex").innerText = params.node.rowIndex;
         document.querySelector("#scriptFullname").innerText = params.data.fullname;

         let statusDropdown = document.querySelector("#targetStatus");
         statusDropdown.options.length = 0;

         let currentStatus = params.data.status;

         if(currentStatus === "FAILED" || currentStatus === "REJECTED"){
             Object.keys(resetFromRejected).forEach(state => {
                 let option = document.createElement('option');
                 option.setAttribute('value', resetFromRejected[state]);
                 option.innerText = state;
                 statusDropdown.add(option);
             });
         } else if (currentStatus === "REVIEWABLE") {
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
