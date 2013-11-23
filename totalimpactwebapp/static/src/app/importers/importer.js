angular.module('importers.importer', [
  'directives.forms',
  'services.loading',
  'resources.users',
  'resources.products',
  'update.update',
  'profile'
])
angular.module('importers.importer')
.factory('Importer', function(Loading, Products, UsersProducts, UsersAbout){
  var waitingOn = {}
  var tiidsAdded = []
  var onImportCompletion = function(){console.log("onImportCompletion(), override me.")}

  var finish = function(importJobName){
    waitingOn[importJobName] = false;
    if (!_.some(_.values(waitingOn))) { // we're not waiting on anything...
      Loading.finish('saveButton')
      onImportCompletion()
    }
  }

  var start = function(importJobName){
    Loading.start("saveButton")
    waitingOn[importJobName] = true
  }


  var saveProducts = function(url_slug, importerName, userInput){
    start("saveProducts")
    Products.save(
      {'importerName': importerName}, // define the url
      userInput, // the post data, from user input
      function(resp, headers){  // run when the server gives us something back.
        var tiids;

        if (resp.error){
          tiids = []
        }
        else {
          tiids = _.keys(resp.products)
        }

        console.log("importer got us some tiids:", tiids);
        tiidsAdded = tiids

        // add the new products to the user's profile on the server
        UsersProducts.patch(
          {id: url_slug},  // the url
          {"tiids": tiids},  // the POST data
          function(){
            finish("saveProducts")
          }
        )
      }
    )
  }

  var saveExternalUsername = function(url_slug, importerName, userInput, saveUsername){
    if (!saveUsername) {
      console.log("no username.")
      return false
    }
    var patchData = {about:{}}
    patchData.about[importerName + "_id"] = userInput
    console.log("trying to save this patch data: ", patchData)

    start("saveExternalUsernames")
    console.log("saving usernames.")
    UsersAbout.patch(
      {id:url_slug},
      patchData,
      function(){
        finish("saveExternalUsernames")
      }
    )




  }


  return {
    'saveProducts': saveProducts,
    'saveExternalUsername': saveExternalUsername,
    setOnImportCompletion: function(callback){
      onImportCompletion = callback
    },
    getTiids: function(){return tiidsAdded}
  }
})


.controller('importerCtrl', function($scope, $location, Products, UserProfile, UsersProducts, Importer, Loading, Update){

  var getUserSlug = function(){
    var re = /\/(\w+)\/products/
    var res = re.exec($location.path())
    return res[1]
  }
  $scope.showImporterWindow = function(){
    if (!$scope.importerHasRun) { // only allow one import for this importer.
      $scope.importWindowOpen = true;
      $scope.importer.userInput = null  // may have been used before; clear it.
    }
  }
  $scope.products = []
  $scope.userInput = {
  }
  $scope.importerHasRun = false

  $scope.onCancel = function(){
    $scope.importWindowOpen = false;
  }

  $scope.onImport = function(){

    // define vars
    var slug = getUserSlug()
    Importer.setOnImportCompletion(
      function(){
        // close the window
        $scope.importWindowOpen = false;
        $scope.products = Importer.getTiids();

        // redirectAfterImport or not (inherits this from parent scope)
        if ($scope.redirectAfterImport) { // inherited from parent scope
          Update.showUpdate(slug, function(){$location.path("/"+slug)})
        }
        $scope.importerHasRun = true
      }
    )

    // ok, let's do this
    console.log(
      _.sprintf("calling /importer/%s updating '%s' with userInput:", $scope.importer.endpoint, slug),
      $scope.userInput
    )


    Importer.saveProducts(slug, $scope.importer.endpoint, $scope.userInput)
    Importer.saveExternalUsername(slug,
                                  $scope.importer.endpoint,
                                  $scope.userInput.input,
                                  $scope.importer.saveUsername)


  }
})
  .directive("ngFileSelect",function(){
    return {
      link: function($scope, el, attrs){
        el.bind("change", function(e){
          var reader = new FileReader()
          reader.onload = function(e){
            // file input is always the primary one. sure, why not.
            $scope.userInput.primary = reader.result
          }

          var file = (e.srcElement || e.target).files[0];
          reader.readAsText(file)
        })
      }
    }
  })
