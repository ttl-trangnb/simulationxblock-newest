try {
  (function (require) {
    require.config({
      paths: {
        'socket.io': "https://cdn.socket.io/4.6.1/socket.io.min", // avoid using .js
      },
    });
  }).call(this, require || RequireJS.require);
} catch (e) {
  console.log("Unable to load Socket.IO via requirejs");
}
