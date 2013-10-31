angular.module("profileProduct", [
    'resources.users',
    'product.product',
    'services.loading',
    'ui.bootstrap',
    'security'
  ])



  .config(['$routeProvider', function ($routeProvider) {

    $routeProvider.when("/:url_slug/product/:tiid", {
      templateUrl:'profile-product/profile-product-page.tpl.html',
      controller:'ProfileProductPageCtrl'
    });

  }])

  .controller('ProfileProductPageCtrl', function ($scope, $routeParams, $modal, security, UsersProduct, UsersAbout, Product, Loading) {

    var slug = $routeParams.url_slug
    Loading.start()

    $scope.userSlug = slug
    $scope.loading = Loading

    $scope.profileAbout = UsersAbout.get({
        id: slug,
        idType: "url_slug"
    })
    $scope.openInfoModal = function(){
      $modal.open({templateUrl: "profile-product/percentilesInfoModal.tpl.html"})
    }
    // this modal stuff should go in it's own controller i think.
//    var percentilesInfoModal = null;
//    $scope.openPercentilesInfoModal = function() {
//      console.log("openPercentilesInfoModal() fired.")
//      percentilesInfoModal = $dialog.dialog({
//        templateUrl: "profile-product/percentilesInfoModal.tpl.html"
//      });
//      percentilesInfoModal.open();
//    }
//
//    $scope.closeModal = function() {
//      console.log("closeModal fired.", percentilesInfoModal)
//      if (percentilesInfoModal) {
//        percentilesInfoModal.close(success);
//        percentilesInfoModal = null;
//      }
//    }


    $scope.product = UsersProduct.get({
      id: slug,
      tiid: $routeParams.tiid,
      idType: "url_slug"
    },
    function(data){
      console.log("data", data)
      $scope.biblio = Product.makeBiblio(data)
      $scope.metrics = Product.makeMetrics(data)
      Loading.finish()
    }
    )
  })

  .controller('modalCtrl')
