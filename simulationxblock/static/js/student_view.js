var contentUserDataUrl = null;
var contentxResultSaveUrl = null;
var socket = null; // need retry if connect fail

function OfficeQuestionBankXBlockStudent(runtime, element, args) {
  contentUserDataUrl = runtime.handlerUrl(element, "user_interaction_data");
  contentxResultSaveUrl = runtime.handlerUrl(element, "result_handler");
  let isSubmitted = false;
  let statusConnectionAddin = false;
  let isTrackingOnlyCOM;
  const trackingOnlyApp = args?.tracking_only_app;
  const msgLostConnect = "Kết nối bị ngắt, vui lòng thử kết nối lại (F5) trước khi tiếp tục làm bài. Hoặc liên hệ với quản trị để được giúp đỡ";
  
  console.log(args);

  const definitions = $.parseJSON(args.state_definitions);
  if(definitions){
    isTrackingOnlyCOM = definitions[0]?.trackingOnlyCOM;
  }
  
  $("#question-text").empty();
  $.each(definitions, function (i, o) {
    $("#question-text").append(`<div>${o.question}</div>`);
  });

  $("#submit-answer").click(() => {
    console.log("submit-answer");
    if (!trackingOnlyApp) {
      if (!statusConnectionAddin && !isTrackingOnlyCOM) {
        $("#feedback").text(msgLostConnect);
        console.log("Mất kết nối socket của addin");
        return;
      }
    }

    $("#feedback").text("Đang gửi bài...");

    console.log(`trackingOnlyApp: ${trackingOnlyApp}`);
    if (trackingOnlyApp) {
      const oCollect = {
        type: "collection",
        command: "execute",
        user: "XBlock",
        recipientId: "XBlock",
        message: { type: "collection" },
      };
      console.log(oCollect);

      // Send result to server
      socket.emit("clientMessage", oCollect);
      return;
    }

    console.log(`isTrackingOnlyCOM: ${isTrackingOnlyCOM}`);
    if(isTrackingOnlyCOM){
      const oCollect = {
        command: "execute",
        user: "XBlock",
        recipientId: "client-com-addin",
        message: JSON.stringify({
          type: "submit-answer",
        }),
      };
      console.log(oCollect);

      // Send result to server
      socket.emit("clientMessage", oCollect);
      return;
    }

    console.log(`send message: submit to client addin`);
    // Send a message with addin
    socket.emit("clientMessage", {
      command: "execute",
      user: "XBlock",
      recipientId: "client-addin",
      message: JSON.stringify({
        type: "submit-answer",
      }),
    });

    // // check submit save result to database
    // handleCommand({
    //     type: 'submit-result',
    // });
  });

  function initSocketLocal(socketIo) {
    socket = socketIo("http://localhost:12345"); // need retry if connect fail
    let logDiv = document.getElementById("log");

    function logToDiv(message) {
      var logMessage = document.createElement("p");
      logMessage.textContent = message;
      // logDiv.appendChild(logMessage);

      console.log("logToDiv: ", message);
    }

    socket.on("connect", () => {
      logToDiv(`Connected to Socket.IO server: , ${socket.id}`);

      $("#feedback").text("Đang khởi tạo...");
      // $("#feedback").text("Đang làm bài...");

      // Send a message
      socket.emit("clientMessage", {
        command: "connect",
        user: "XBlock",
        message: "",
      });
    });

    socket.on("serverMessage", (data) => {
      handleCommand(data);
    });

    socket.on("response", (data) => {
      console.log("Response from server:", data);
      logToDiv("Message received: " + JSON.stringify(data));
    });

    socket.on("disconnect", () => {
      console.log("Disconnected from Socket.IO server");
      logToDiv("Disconnected from Socket.IO server");
      $("#feedback").text("Vui lòng chờ kết nối lại trước khi tiếp tục");
    });
  }

  // avoid initialization socket anytime after change
  if (socket != null || socket?.connected) socket.disconnect();

  if (typeof require === "function") {
    require(["socket.io"], function (io) {
      initSocketLocal(io);
    });
  } else {
    loadSocketJS(function () {
      initSocketLocal(window.io);
    });
  }

  async function handleCommand(command) {
    console.log(command);
    if (command === null) {
      console.log("Data error");
      return;
    }
    if (typeof command === "string") command = parseJson(command);
    if (typeof command !== "object") {
      console.log("Data error parseJson");
      return;
    }
    const data = command;

    switch (data?.type) {
      case "connected":
        // console.log(args.app);
        if (data?.user === "XBlock") {
          let json = {
            command: "start",
            user: "XBlock",
            message: args.app,
          };
          json["browser"] = browserDetect();
          const title = document.getElementsByTagName("title")[0].innerHTML;
          json["title"] = title;
          if (args?.template) json["template"] = args.template;
          if (trackingOnlyApp) {
            sendSettings(""); // send setting to app
            $("#feedback").text("Khởi tạo thành công");
            return;
          }
          socket.emit("clientMessage", json);
        }

        const aUsersReceiveSettings = ["client-addin", "client-com-addin"];
        if (aUsersReceiveSettings.includes(data?.user)) {
          sendSettings(data?.user);
          $("#feedback").text("Đang làm bài...");
          statusConnectionAddin = true;
          // args.type = "send-settings";
          // socket.emit("clientMessage", {
          //   command: "execute",
          //   user: "XBlock",
          //   recipientId: "client-addin",
          //   type: args.type,
          //   message: JSON.stringify(args),
          // });
        }
        break;
      case "init-app-done":
        // wait socket in add in handshake and connect
        setTimeout(function () {
          if (!statusConnectionAddin) {
            $("#feedback").text(msgLostConnect);
          }
        }, 1500);
        break;
      case "collection":
        const dataCollect = data.message;
        let finalState = {};
        if (dataCollect) {
          for (let i = 0; i < dataCollect.length; i++) {
            if (!dataCollect[i]) continue;
            for (var key in dataCollect[i]) {
              finalState[key] = dataCollect[i][key];
            }
          }
        }
        postResult(finalState);
        break;
      case "submit-result":
        console.log(data);
        postResult(data.finalState);
        break;
      case "update-clients":
        console.log(command.clients);
        if (command.clients && Array.isArray(command.clients)) {
          if (!isSubmitted) {
            // for case addin js disconnect
            if (!command.clients.includes("client-addin")) {
              if(!isTrackingOnlyCOM){
                $("#feedback").text(msgLostConnect);
              }
            } else {
              console.log("Khởi tạo thành công");
              $("#feedback").text("Khởi tạo thành công");
              statusConnectionAddin = true;
            }
          }
        }
        // $('#status-socket').html();
        // $("#feedback").text("Stopped, please wait retry connect before continue");
        console.log(command);
        break;
      case "close":
        // wait application close, close socket then reset state
        setTimeout(() => {
          isSubmitted = false;
          statusConnectionAddin = false;
        }, 2000);
        break;
      default:
        console.warn("Unknown command:", command);
        break;
    }
  }

  function sendSettings(recipientId = "client-addin") {
    args.type = "send-settings";
    socket.emit("clientMessage", {
      command: "execute",
      user: "XBlock",
      recipientId: recipientId,
      type: args.type,
      message: JSON.stringify(args),
    });
  }

  function postResult(finalState) {
    try {
      $.ajax({
        type: "POST",
        url: contentxResultSaveUrl,
        data: JSON.stringify({
          actor: {
            mbox: "mailto:" + args.user_email,
            objectType: "Agent",
          },
          finalState: finalState,
        }),
      })
        .done(function (...response) {
          console.log(response);
          isSubmitted = true;
          $("#feedback").text("Gửi bài trả lời câu hỏi thành công!");
          
          // Send a message close application after receive
          socket.emit("clientMessage", {
            command: "close",
            user: "XBlock",
            message: "",
          });
        })
        .fail(function (...fail) {
          console.log(fail);
          $("#feedback").text("Gửi bài xảy ra lỗi. Vui lòng thử lại");
        });
    } catch (error) {
      console.error(error);
      $("#feedback").text("Gửi bài xảy ra lỗi. Vui lòng thử lại");
    }
  }

  function parseJson(str) {
    try {
      return JSON.parse(str);
    } catch (e) {
      return null;
    }
  }

  const browserDetect = function () {
    var nav = window.navigator,
      ua = window.navigator.userAgent.toLowerCase();
    // Detect browsers (only the ones that have some kind of quirk we need to work around)
    if (
      nav.appName.toLowerCase().indexOf("microsoft") != -1 ||
      nav.appName.toLowerCase().match(/trident/gi) !== null
    )
      return "IE";
    if (ua.match(/chrome/gi) !== null) return "Chrome";
    if (ua.match(/firefox/gi) !== null) return "Firefox";
    if (ua.match(/safari/gi) !== null) return "Safari";
    if (ua.match(/webkit/gi) !== null) return "Webkit";
    if (ua.match(/gecko/gi) !== null) return "Gecko";
    if (ua.match(/opera/gi) !== null) return "Opera";
    // If any case miss we will return null
    return null;
  };
}

function loadSocketJS(callback) {
  if (window.io) {
    callback();
  } else {
    $.getScript("https://cdn.socket.io/4.6.1/socket.io.min.js")
      .done(function () {
        if (typeof io !== "undefined") {
          window.io = io;
          callback();
        }
      })
      .fail(function () {
        console.error("Error loading socket.io.");
      });
  }
}
