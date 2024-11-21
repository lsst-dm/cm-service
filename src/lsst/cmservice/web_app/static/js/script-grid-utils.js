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

const resetScriptModal = document.querySelector("#modalDialog");
const errorModal = document.querySelector("#errorModal");
const closeErrModalBtn = document.querySelector("[close-error-modal]");
closeErrModalBtn.addEventListener("click", () => errorModal.close());
const errorMessage = document.querySelector("[error-message]")

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
            // Object.keys(resetFromRejected).forEach(state => {
            //     // ajax form submit
            //     // var xhr = new XMLHttpRequest();
            //     // xhr.open("POST", '/server', true);
            //     //
            //     // //Send the proper header information along with the request
            //     // xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
            //     //
            //     // xhr.onreadystatechange = function() { // Call a function when the state changes.
            //     //     if (this.readyState === XMLHttpRequest.DONE && this.status === 200) {
            //     //         // Request finished. Do processing here.
            //     //     }
            //     // }
            //     // xhr.send("foo=bar&lorem=ipsum");
            //
            //      let option = document.createElement('option');
            //      option.setAttribute('value', resetFromRejected[state]);
            //      option.innerText = state;
            //      statusDropdown.add(option);
            //  });
         resetScriptModal.showModal();
        });
    }

    getGui() {
        return this.eGui;
  }
}

const closeModal = () => {
  resetScriptModal.close();
};

const updateStatus = () => {
    let resetObj = {
        fullname: String(document.querySelector("#scriptFullname").innerText),
        status: parseInt(document.querySelector("#targetStatus").value),
    };

    let resetJson = JSON.stringify(resetObj);
    console.log(resetJson);

    const url = "{{url_for('reset_script')}}";
    let xhr = new XMLHttpRequest();
    xhr.open('POST', url, true);
    xhr.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
    xhr.onload = function () {
        console.log(xhr.responseText);

        if (xhr.status === 201) {
            const rowIndex = Number(document.querySelector("#rowIndex").innerText);
            const newStatus = document.querySelector("#targetStatus").value;
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

class ScriptNameRenderer {
    eGui;
    init(params) {
        let scriptName = document.createElement('a');
        scriptName.textContent = params.data.name;
        scriptName.href = `{{url_for("get_script", campaign_id=campaign_id, step_id=step.id, script_id="${params.data.id}")}}`;
        scriptName.setAttribute('class', 'font-bold text-teal-700 underline underline-offset-4 decoration-2 hover:text-gray-500');
        this.eGui = document.createElement('span');
        this.eGui.appendChild(scriptName)
    }

     getGui() {
        return this.eGui;
     }

     refresh(params) {
        return false;
     }
}

const scriptsGridOptions = {
    columnDefs: [
        {field: "name", flex: 1, cellRenderer: ScriptNameRenderer,},
        {field: "status", flex: 1},
        {field: "superseded", flex: 1},
        {
            headerName: 'Actions',
            field: 'editButton',
            cellRenderer: ResetButtonCellRenderer,
            editable: false,
            width: 200,
        },
    ]
};
